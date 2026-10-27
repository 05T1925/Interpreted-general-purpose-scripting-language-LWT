"""Fixed, read-only LWT teaching examples executed through the public CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT_SECONDS = 12


@dataclass(frozen=True)
class LabExample:
    id: str
    title: str
    source_path: str
    spec_reference: str
    observation: str
    program_args: tuple[str, ...]
    stdin_text: str
    expected_exit_code: int
    expected_stdout: str
    expected_error_category: str | None = None
    expected_location: tuple[int, int] | None = None
    expected_error_message: str | None = None


EXAMPLES: tuple[LabExample, ...] = (
    LabExample(
        id="control-flow",
        title="分支与循环",
        source_path="examples/control_flow.lwt",
        spec_reference="语言规范 §3 语法、§4.1 算术与 §5.2 条件和循环",
        observation="预测循环每次输出的正负号，以及循环结束时的值；负数取自 % 与条件分支。",
        program_args=(),
        stdin_text="",
        expected_exit_code=0,
        expected_stdout="0\n-1\n2\n-3\n",
    ),
    LabExample(
        id="functions",
        title="函数、前向调用与递归",
        source_path="examples/functions.lwt",
        spec_reference="语言规范 §3 顶层声明、§5.3 函数",
        observation="调用出现在函数声明之前；递归在 n <= 1 时返回 1。预测 factorial(5) 的输出。",
        program_args=(),
        stdin_text="",
        expected_exit_code=0,
        expected_stdout="120\n",
    ),
    LabExample(
        id="collections",
        title="数组、record 与 each 浅快照",
        source_path="examples/collections.lwt",
        spec_reference="语言规范 §4.3 数组和 record、§5.4 each",
        observation="遍历开始时保存数组元素引用的浅快照。预测替换和追加怎样影响本轮访问，以及对 record 的修改是否可见。",
        program_args=(),
        stdin_text="",
        expected_exit_code=0,
        expected_stdout=(
            "draft\nreview\n"
            "[\"draft\", \"review\"]\n"
            "[Task{name: \"draft\", done: true}, "
            "Task{name: \"replacement\", done: false}, "
            "Task{name: \"late\", done: false}]\n"
        ),
    ),
    LabExample(
        id="text-cli",
        title="文本内置函数与 CLI 参数",
        source_path="examples/text_tools.lwt",
        spec_reference="语言规范 §6 预置函数与 CLI 参数",
        observation="-- 后的路径和 preview 是 args() 的两个元素；read_text、trim、split、to_int、str 与 len 都由 LWT 程序执行。",
        program_args=("examples/fixtures/text_tools.txt", "preview"),
        stdin_text="",
        expected_exit_code=0,
        expected_stdout='2\n[12, "apple", 5]\n[7, "pear", 4]\n',
    ),
    LabExample(
        id="stdin",
        title="标准输入与 emit",
        source_path="examples/basic_io.lwt",
        spec_reference="语言规范 §6 input() 与 emit",
        observation="本次 stdin 提供一行中文文本；input() 去掉行末换行后返回字符串，再由 emit 输出。",
        program_args=(),
        stdin_text="LWT 输入演示\n",
        expected_exit_code=0,
        expected_stdout="Enter one line:\nLWT 输入演示\n",
    ),
    LabExample(
        id="runtime-error",
        title="运行时错误定位",
        source_path="examples/language_lab/division_by_zero.lwt",
        spec_reference="语言规范 §4.1 除零、§7 运行时诊断",
        observation="预测退出码与 stderr 的类别、行列位置。正确的诊断是可观察输出，不是 Python 异常回溯。",
        program_args=(),
        stdin_text="",
        expected_exit_code=3,
        expected_stdout="",
        expected_error_category="RuntimeError",
        expected_location=(2, 8),
        expected_error_message="division by zero",
    ),
)

_EXAMPLES_BY_ID = {example.id: example for example in EXAMPLES}


class LanguageLabError(RuntimeError):
    """A readable failure while loading or running a bundled lab example."""


@dataclass(frozen=True)
class LabResult:
    example: LabExample
    source_text: str
    command: tuple[str, ...]
    working_directory: Path
    stdin_text: str
    stdout: str
    stderr: str
    returncode: int
    expectation_met: bool


def get_example(example_id: str) -> LabExample:
    """Return one item from the immutable teaching-example allowlist."""

    try:
        return _EXAMPLES_BY_ID[example_id]
    except KeyError as error:
        raise LanguageLabError("未找到该语义实验示例。") from error


def load_source(example_id: str) -> tuple[LabExample, str]:
    example = get_example(example_id)
    source_path = (PROJECT_ROOT / example.source_path).resolve()
    try:
        source_path.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise LanguageLabError("示例源码路径超出项目目录。") from error
    try:
        source_text = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise LanguageLabError(f"无法读取示例源码：{example.source_path}") from error
    return example, source_text


def _matches_expectation(example: LabExample, completed: subprocess.CompletedProcess[str]) -> bool:
    if completed.returncode != example.expected_exit_code:
        return False
    if completed.stdout != example.expected_stdout:
        return False
    if example.expected_error_category is None:
        return completed.stderr == ""
    if not completed.stderr:
        return False
    if example.expected_location is not None:
        line, column = example.expected_location
        marker = rf":{line}:{column}: {re.escape(example.expected_error_category)}:"
        if re.search(marker, completed.stderr) is None:
            return False
    elif f": {example.expected_error_category}:" not in completed.stderr:
        return False
    if example.expected_error_message is not None:
        if example.expected_error_message not in completed.stderr:
            return False
    return True


def run_example(
    example_id: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> LabResult:
    """Run one allowlisted source file via ``python -m lwt``."""

    example, source_text = load_source(example_id)
    source_path = str((PROJECT_ROOT / example.source_path).resolve())
    command = [sys.executable, "-m", "lwt", source_path]
    if example.program_args:
        command.extend(("--", *example.program_args))
    process_runner = runner or subprocess.run
    try:
        completed = process_runner(
            command,
            cwd=PROJECT_ROOT,
            input=example.stdin_text,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise LanguageLabError(f"示例运行超过 {timeout:g} 秒，已停止；可重试。") from error
    except OSError as error:
        raise LanguageLabError(f"无法启动 LWT CLI：{error}") from error
    except ValueError as error:
        raise LanguageLabError(f"LWT CLI 调用参数无效：{error}") from error

    return LabResult(
        example=example,
        source_text=source_text,
        command=tuple(command),
        working_directory=PROJECT_ROOT,
        stdin_text=example.stdin_text,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        returncode=completed.returncode,
        expectation_met=_matches_expectation(example, completed),
    )


class LabSession:
    """Track selection and reject results from an obsolete request."""

    def __init__(self) -> None:
        self.revision = 0
        self.selected_id: str | None = None
        self.pending: int | None = None
        self.result: LabResult | None = None
        self.error: str | None = None

    def select(self, example_id: str | None) -> None:
        if example_id is not None:
            get_example(example_id)
        self.revision += 1
        self.selected_id = example_id
        self.pending = None
        self.result = None
        self.error = None

    def begin(self) -> int:
        if self.selected_id is None:
            raise LanguageLabError("请先选择一个语义示例。")
        if self.pending is not None:
            raise LanguageLabError("当前示例正在运行。")
        self.revision += 1
        self.pending = self.revision
        self.result = None
        self.error = None
        return self.revision

    def complete(
        self, revision: int, result: LabResult | None, error: str | None = None
    ) -> bool:
        if self.pending != revision or self.revision != revision:
            return False
        self.pending = None
        self.result = result
        self.error = error
        return True
