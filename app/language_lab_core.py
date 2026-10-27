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
class PredictionQuestion:
    prompt: str
    options: tuple[str, ...]
    correct_option: str
    explanation: str


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
    prediction: PredictionQuestion
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
        prediction=PredictionQuestion(
            prompt="循环中的 emit 会按什么顺序输出？",
            options=("0 → -1 → 2 → -3", "0 → 1 → 2 → 3", "只输出 0"),
            correct_option="0 → -1 → 2 → -3",
            explanation=(
                "i 从 0 增加到 3。偶数分支输出 i，奇数分支输出 -i；"
                "当 i 变成 4 时 while 条件为假。"
            ),
        ),
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
        prediction=PredictionQuestion(
            prompt="factorial(5) 在函数声明之前调用，结果是什么？",
            options=("120", "24", "声明前调用会报未定义函数"),
            correct_option="120",
            explanation=(
                "顶层函数在执行语句前登记，因此可以前向调用；递归在 n <= 1 时返回 1，"
                "factorial(5) 的结果是 120。"
            ),
        ),
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
        prediction=PredictionQuestion(
            prompt="each 本轮会访问被替换的 review 或新追加的 late 吗？",
            options=(
                "访问 draft、review；不访问 replacement 或 late",
                "访问 draft、replacement、late",
                "只访问 draft",
            ),
            correct_option="访问 draft、review；不访问 replacement 或 late",
            explanation=(
                "each 开始时复制数组元素引用形成浅快照：之后替换数组位置不会替换快照里的引用，"
                "追加项不进入本轮；对快照引用到的 record 修改仍然可见。"
            ),
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
        prediction=PredictionQuestion(
            prompt="args() 会返回几个 -- 后的程序参数？",
            options=("1 个", "2 个", "3 个"),
            correct_option="2 个",
            explanation=(
                "分隔符后的路径和 preview 都是程序参数，所以 args() 有两个元素；"
                "预期 stdout 第一行也就是 2。"
            ),
        ),
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
        prediction=PredictionQuestion(
            prompt="input() 返回的文本会保留 stdin 行末的 LF 吗？",
            options=("会保留 LF", "不会保留 LF", "会返回 null"),
            correct_option="不会保留 LF",
            explanation=(
                "input() 去掉读入行的 LF（也处理 CRLF 行结束），返回正文字符串；"
                "随后 emit 为正文输出一行。"
            ),
        ),
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
        prediction=PredictionQuestion(
            prompt="除零程序的错误类别、位置和退出码是什么？",
            options=("exit 0，无诊断", "exit 2，SyntaxError", "exit 3，RuntimeError，2:8"),
            correct_option="exit 3，RuntimeError，2:8",
            explanation=(
                "除零在运行阶段失败，CLI 使用运行时错误退出码 3；除法运算符位于第 2 行第 8 列，"
                "stderr 给出 RuntimeError 诊断，不输出 Python traceback。"
            ),
        ),
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


def describe_outcome(result: LabResult) -> str:
    """Name the observed CLI outcome without interpreting or recomputing it."""

    if not result.expectation_met:
        return "与记录预期不同"
    if result.example.expected_error_category is not None:
        return f"按预期报告 {result.example.expected_error_category}"
    return "成功，符合 stdout 与退出码预期"


class LabSession:
    """Track selection and reject results from an obsolete request."""

    def __init__(self) -> None:
        self.revision = 0
        self.selected_id: str | None = None
        self.pending: int | None = None
        self.result: LabResult | None = None
        self.error: str | None = None
        self.prediction_choice: str | None = None
        self.prediction_submitted = False
        self.prediction_correct: bool | None = None
        self.closed = False

    def select(self, example_id: str | None) -> None:
        if self.closed:
            raise LanguageLabError("语义实验室会话已关闭。")
        if example_id is not None:
            get_example(example_id)
        self.revision += 1
        self.selected_id = example_id
        self.pending = None
        self.result = None
        self.error = None
        self.prediction_choice = None
        self.prediction_submitted = False
        self.prediction_correct = None

    def choose_prediction(self, option: str) -> None:
        if self.selected_id is None:
            raise LanguageLabError("请先选择一个语义示例。")
        if self.pending is not None:
            raise LanguageLabError("示例正在运行，暂不能更改预测。")
        if self.prediction_submitted:
            raise LanguageLabError("预测已提交；如需重做，请重置本例。")
        question = get_example(self.selected_id).prediction
        if option not in question.options:
            raise LanguageLabError("请选择本题中的一个预测选项。")
        self.prediction_choice = option
        self.prediction_correct = None

    def submit_prediction(self) -> bool:
        if self.selected_id is None:
            raise LanguageLabError("请先选择一个语义示例。")
        if self.pending is not None:
            raise LanguageLabError("示例正在运行，暂不能提交预测。")
        if self.prediction_submitted:
            raise LanguageLabError("本次预测已经提交。")
        if self.prediction_choice is None:
            raise LanguageLabError("请先选择一个预测选项。")
        question = get_example(self.selected_id).prediction
        self.prediction_submitted = True
        self.prediction_correct = self.prediction_choice == question.correct_option
        self.result = None
        self.error = None
        return self.prediction_correct

    def reset_lesson(self) -> None:
        if self.closed:
            raise LanguageLabError("语义实验室会话已关闭。")
        if self.pending is not None:
            raise LanguageLabError("示例正在运行，暂不能重置。")
        self.select(self.selected_id)

    def close(self) -> None:
        self.revision += 1
        self.selected_id = None
        self.pending = None
        self.result = None
        self.error = None
        self.prediction_choice = None
        self.prediction_submitted = False
        self.prediction_correct = None
        self.closed = True

    def begin(self) -> int:
        if self.closed:
            raise LanguageLabError("语义实验室会话已关闭。")
        if self.selected_id is None:
            raise LanguageLabError("请先选择一个语义示例。")
        if self.pending is not None:
            raise LanguageLabError("当前示例正在运行。")
        if not self.prediction_submitted:
            raise LanguageLabError("请先提交预测，再运行示例。")
        if self.result is not None or self.error is not None:
            raise LanguageLabError("本例已有运行结果；重置后可以重新预测并运行。")
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
