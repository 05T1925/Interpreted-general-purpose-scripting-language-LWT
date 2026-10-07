"""Headless query and game-state logic for the LWT Log Detective GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYZER_SOURCE = PROJECT_ROOT / "app" / "log_report.lwt"
DEFAULT_LOG = PROJECT_ROOT / "app" / "fixtures" / "sample.log"
QUERY_TIMEOUT_SECONDS = 20
MATCHED_RECORDS_PREFIX = "Matched records:"


@dataclass(frozen=True)
class GameQuestion:
    """A prompt and CLI filters; its answer is always computed by LWT."""

    condition: str
    filter_args: tuple[str, ...]


QUESTIONS: tuple[GameQuestion, ...] = (
    GameQuestion("Level 精确等于 INFO", ("--level", "INFO")),
    GameQuestion("Level 精确等于 WARN", ("--level", "WARN")),
    GameQuestion("Message 包含关键词 retry", ("--keyword", "retry")),
    GameQuestion("Level 精确等于 ERROR", ("--level", "ERROR")),
    GameQuestion(
        "Level 等于 WARN 且 Message 包含 retry",
        ("--level", "WARN", "--keyword", "retry"),
    ),
)


class AnalyzerError(RuntimeError):
    """A user-facing failure while invoking or reading the LWT analyzer."""


@dataclass(frozen=True)
class AnalysisResult:
    matched_records: int
    report: str


def build_lwt_command(
    log_path: str | Path,
    filter_args: Sequence[str] = (),
) -> list[str]:
    """Build argv for the public CLI while preserving each argument boundary."""

    resolved_log_path = Path(log_path).expanduser().resolve()
    return [
        sys.executable,
        "-m",
        "lwt",
        str(ANALYZER_SOURCE),
        "--",
        str(resolved_log_path),
        *filter_args,
    ]


def parse_matched_records(report: str) -> int:
    """Read exactly one valid ``Matched records: N`` line from LWT output."""

    matching_lines = [
        line for line in report.splitlines() if line.startswith(MATCHED_RECORDS_PREFIX)
    ]
    if not matching_lines:
        raise AnalyzerError("LWT 报告缺少 Matched records 字段。")
    if len(matching_lines) != 1:
        raise AnalyzerError("LWT 报告包含重复的 Matched records 字段。")

    value = matching_lines[0][len(MATCHED_RECORDS_PREFIX) :]
    if re.fullmatch(r" [0-9]+", value) is None:
        raise AnalyzerError("LWT 报告中的 Matched records 必须是非负十进制整数。")
    try:
        return int(value[1:])
    except ValueError as error:
        raise AnalyzerError("LWT 报告中的 Matched records 超出当前 Python 的整数转换限制。") from error


def run_lwt_report(
    log_path: str | Path,
    filter_args: Sequence[str] = (),
    *,
    timeout: float = QUERY_TIMEOUT_SECONDS,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> str:
    """Run the existing LWT program and return its complete UTF-8 report."""

    command = build_lwt_command(log_path, filter_args)
    process_runner = runner or subprocess.run
    try:
        completed = process_runner(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise AnalyzerError(
            f"LWT 日志分析超过 {timeout:g} 秒，已停止本次查询。"
        ) from error
    except OSError as error:
        raise AnalyzerError(f"无法启动 LWT 分析器：{error}") from error
    except ValueError as error:
        raise AnalyzerError(f"LWT 分析器调用参数无效：{error}") from error

    if completed.returncode != 0:
        diagnostic = (completed.stderr or "").strip()
        if not diagnostic:
            diagnostic = f"LWT CLI 退出码为 {completed.returncode}。"
        raise AnalyzerError(f"LWT 日志分析失败：{diagnostic}")
    if not isinstance(completed.stdout, str):
        raise AnalyzerError("LWT 分析器没有返回可读取的文本报告。")
    return completed.stdout


def analyze_question(
    log_path: str | Path,
    question: GameQuestion,
    *,
    timeout: float = QUERY_TIMEOUT_SECONDS,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> AnalysisResult:
    """Get a game answer from the LWT report, keeping the full report available."""

    report = run_lwt_report(
        log_path,
        question.filter_args,
        timeout=timeout,
        runner=runner,
    )
    return AnalysisResult(parse_matched_records(report), report)


def full_report(
    log_path: str | Path,
    *,
    timeout: float = QUERY_TIMEOUT_SECONDS,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> str:
    """Return the unfiltered report produced by the public LWT CLI."""

    return run_lwt_report(log_path, timeout=timeout, runner=runner)


class GameSession:
    """Small deterministic state machine, independent of Tkinter."""

    def __init__(self, questions: Sequence[GameQuestion] = QUESTIONS) -> None:
        if not questions:
            raise ValueError("a game session needs at least one question")
        self.questions = tuple(questions)
        self.restart()
        self.started = False

    @property
    def question_count(self) -> int:
        return len(self.questions)

    @property
    def round_number(self) -> int:
        return self.index + 1

    @property
    def current_question(self) -> GameQuestion:
        if not self.started or self.finished:
            raise RuntimeError("there is no active question")
        return self.questions[self.index]

    def start(self) -> None:
        self.restart()
        self.started = True

    def restart(self) -> None:
        self.index = 0
        self.score = 0
        self.finished = False
        self.answered = False
        self.last_answer: int | None = None
        self.correct_answer: int | None = None

    def submit(self, answer: int, correct_answer: int) -> bool:
        if not self.started or self.finished:
            raise RuntimeError("the game is not accepting an answer")
        if self.answered:
            raise RuntimeError("this question has already been answered")
        if type(answer) is not int or answer < 0:
            raise ValueError("answer must be a non-negative integer")
        if type(correct_answer) is not int or correct_answer < 0:
            raise ValueError("correct answer must be a non-negative integer")

        self.answered = True
        self.last_answer = answer
        self.correct_answer = correct_answer
        is_correct = answer == correct_answer
        if is_correct:
            self.score += 1
        return is_correct

    def advance(self) -> bool:
        if not self.started or self.finished or not self.answered:
            raise RuntimeError("answer the current question before advancing")
        if self.index + 1 == len(self.questions):
            self.finished = True
            return False
        self.index += 1
        self.answered = False
        self.last_answer = None
        self.correct_answer = None
        return True
