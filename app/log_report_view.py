"""Strict view model for the existing LWT log report stdout contract.

This module never opens a log file. All business counts come from the public
python -m lwt report, and the original text remains available for audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.log_detective_core import AnalyzerError, run_lwt_report


_COUNT = re.compile(r"[0-9]+\Z")
_HEADER = "LWT log report"
_FIELDS = ("Total lines", "Valid records", "Malformed lines", "Matched records")
_SECTIONS = ("Level counts:", "Top modules:", "Matching examples (first 3):")


@dataclass(frozen=True)
class CountRow:
    name: str
    count: int


@dataclass(frozen=True)
class LogReport:
    total_lines: int
    valid_records: int
    malformed_lines: int
    matched_records: int
    level_counts: tuple[CountRow, ...]
    top_modules: tuple[CountRow, ...]
    matching_examples: tuple[str, ...]
    raw: str


@dataclass(frozen=True)
class WorkbenchQuery:
    log_path: Path
    level: str
    keyword: str
    top: str

    @classmethod
    def from_fields(
        cls, path: str | Path, level: str = "", keyword: str = "", top: str = "5"
    ) -> "WorkbenchQuery":
        if not top or _COUNT.fullmatch(top) is None:
            raise AnalyzerError("Top 请输入非负 ASCII 十进制整数，例如 0、2 或 5。")
        for label, value in (("Level", level), ("Keyword", keyword)):
            if "\x00" in value or "\n" in value or "\r" in value:
                raise AnalyzerError(f"{label} 不可包含换行或 NUL。")
            if value.startswith("--"):
                raise AnalyzerError(f"{label} 不可用 -- 开头；LWT CLI 会将其识别为选项。")
        return cls(Path(path).expanduser().resolve(), level, keyword, top)

    @property
    def filter_args(self) -> tuple[str, ...]:
        args: list[str] = []
        if self.level:
            args.extend(("--level", self.level))
        if self.keyword:
            args.extend(("--keyword", self.keyword))
        args.extend(("--top", self.top))
        return tuple(args)

    @property
    def signature(self) -> tuple[str, str, str, str]:
        return (str(self.log_path), self.level, self.keyword, self.top)


def _number(text: str, label: str) -> int:
    if _COUNT.fullmatch(text) is None:
        raise AnalyzerError(f"LWT 报告的 {label} 不是非负十进制整数。")
    try:
        return int(text)
    except ValueError as error:
        raise AnalyzerError(f"LWT 报告的 {label} 超出当前 Python 的整数转换限制。") from error


def _rows(lines: list[str], section: str) -> tuple[CountRow, ...]:
    rows: list[CountRow] = []
    names: set[str] = set()
    for line in lines:
        name, separator, count_text = line.rpartition("|")
        if not separator:
            raise AnalyzerError(f"LWT 报告的 {section} 项缺少 | 计数分隔符。")
        count = _number(count_text, section)
        if count == 0:
            raise AnalyzerError(f"LWT 报告的 {section} 项计数必须大于 0。")
        if name in names:
            raise AnalyzerError(f"LWT 报告的 {section} 包含重复名称：{name!r}。")
        names.add(name)
        rows.append(CountRow(name, count))
    return tuple(rows)


def _at_most_top(row_count: int, top: str) -> bool:
    normalized = top.lstrip("0") or "0"
    limit = str(row_count)
    return (len(normalized), normalized) >= (len(limit), limit)


def parse_report(raw: str, *, top: str = "5") -> LogReport:
    """Parse the exact stdout layout emitted by app/log_report.lwt."""

    if not top or _COUNT.fullmatch(top) is None:
        raise AnalyzerError("解析报告时的 Top 参数无效。")
    if not raw.endswith("\n"):
        raise AnalyzerError("LWT 报告缺少末尾换行，可能已截断。")
    lines = raw.splitlines()
    if len(lines) < 8 or lines[0] != _HEADER:
        raise AnalyzerError("LWT 报告标题或固定字段不完整。")

    counts: list[int] = []
    for index, label in enumerate(_FIELDS, start=1):
        prefix = f"{label}: "
        if not lines[index].startswith(prefix):
            raise AnalyzerError(f"LWT 报告缺少或错序：{label}。")
        counts.append(_number(lines[index][len(prefix):], label))
    total, valid, malformed, matched = counts
    if total != valid + malformed:
        raise AnalyzerError("LWT 报告计数矛盾：总行数不等于有效与坏行之和。")
    if matched > valid:
        raise AnalyzerError("LWT 报告计数矛盾：匹配数大于有效记录数。")
    if lines[5] != _SECTIONS[0]:
        raise AnalyzerError("LWT 报告缺少或错序：Level counts。")
    try:
        module_start = lines.index(_SECTIONS[1], 6)
        examples_start = lines.index(_SECTIONS[2], module_start + 1)
    except ValueError as error:
        raise AnalyzerError("LWT 报告缺少 Top modules 或 Matching examples 章节。") from error
    heading_positions = [(line, index) for index, line in enumerate(lines) if line in _SECTIONS]
    if heading_positions != [
        (_SECTIONS[0], 5),
        (_SECTIONS[1], module_start),
        (_SECTIONS[2], examples_start),
    ]:
        raise AnalyzerError("LWT 报告章节重复或顺序错误。")
    if any(
        re.fullmatch(rf"{re.escape(field)}: [0-9]+", line)
        for line in lines[6:]
        for field in _FIELDS
    ):
        raise AnalyzerError("LWT 报告包含重复的固定计数字段。")

    levels = _rows(lines[6:module_start], "Level counts")
    modules = _rows(lines[module_start + 1:examples_start], "Top modules")
    examples = tuple(lines[examples_start + 1:])
    if sum(row.count for row in levels) != matched:
        raise AnalyzerError("LWT 报告计数矛盾：级别合计与匹配数不同。")
    if levels != tuple(sorted(levels, key=lambda row: row.name)):
        raise AnalyzerError("LWT 报告级别顺序错误。")
    if modules != tuple(sorted(modules, key=lambda row: (-row.count, row.name))):
        raise AnalyzerError("LWT 报告模块排行顺序错误。")
    if not _at_most_top(len(modules), top):
        raise AnalyzerError("LWT 报告模块排行超过指定 Top 数量。")
    if sum(row.count for row in modules) > matched:
        raise AnalyzerError("LWT 报告模块排行计数超过匹配数。")
    if len(examples) != min(3, matched):
        raise AnalyzerError("LWT 报告匹配示例数量与匹配数不符。")
    if any(example.count("|") != 3 for example in examples):
        raise AnalyzerError("LWT 报告匹配示例不是四字段记录。")
    return LogReport(total, valid, malformed, matched, levels, modules, examples, raw)


def analyze_workbench(query: WorkbenchQuery) -> LogReport:
    """Run the public LWT CLI once and interpret only its stdout report."""

    return parse_report(run_lwt_report(query.log_path, query.filter_args), top=query.top)


class WorkbenchSession:
    """Keep asynchronous results tied to the exact requested conditions."""

    def __init__(self) -> None:
        self.revision = 0
        self.pending: int | None = None
        self.query: WorkbenchQuery | None = None
        self.report: LogReport | None = None
        self.error: str | None = None

    def invalidate(self) -> None:
        self.revision += 1
        self.query = None
        self.report = None
        self.error = None

    def begin(self, query: WorkbenchQuery) -> int:
        if self.pending is not None:
            raise RuntimeError("a workbench query is already running")
        self.invalidate()
        self.query = query
        self.pending = self.revision
        return self.pending

    def complete(
        self, revision: int, report: LogReport | None, error: str | None = None
    ) -> bool:
        if self.pending != revision:
            return False
        self.pending = None
        if self.revision != revision:
            return False
        self.report = report
        self.error = error
        return True
