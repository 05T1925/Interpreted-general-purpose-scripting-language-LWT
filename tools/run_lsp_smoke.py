#!/usr/bin/env python3
"""Run a deterministic LSP stdio conversation against a real LWT server process."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lwt.lsp_documents import codepoint_to_utf16_character
from lwt.lsp_protocol import encode_message


def _decode_frames(data: bytes) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    offset = 0
    while offset < len(data):
        delimiter = data.find(b"\r\n\r\n", offset)
        if delimiter < 0:
            raise ValueError("stdout contains bytes outside LSP framing")
        header = data[offset:delimiter].decode("ascii", errors="strict")
        lengths = []
        for line in header.split("\r\n"):
            if line.lower().startswith("content-length:"):
                lengths.append(line.split(":", 1)[1].strip())
        if len(lengths) != 1 or not lengths[0].isdecimal():
            raise ValueError("response has invalid Content-Length")
        length = int(lengths[0])
        body_start = delimiter + 4
        body_end = body_start + length
        if body_end > len(data):
            raise ValueError("response body is truncated")
        body = data[body_start:body_end]
        if len(body) != length:
            raise ValueError("response Content-Length does not match UTF-8 bytes")
        value = json.loads(body.decode("utf-8", errors="strict"))
        if not isinstance(value, dict):
            raise ValueError("response must be a JSON object")
        messages.append(value)
        offset = body_end
    return messages


def _position(text: str, needle: str, line_index: int = 0) -> dict[str, int]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    line = lines[line_index]
    start = line.index(needle)
    return {
        "line": line_index,
        "character": codepoint_to_utf16_character(line, start),
    }


def _message(method: str, *, request_id: int | None = None, params=None) -> dict[str, object]:
    item: dict[str, object] = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        item["id"] = request_id
    if params is not None:
        item["params"] = params
    return item


def run(output: Path) -> dict[str, object]:
    source_path = ROOT / "examples" / "modules" / "main.lwt"
    text = source_path.read_text(encoding="utf-8")
    uri = source_path.as_uri()
    broken_text = text + "missing();\n"
    sequence = [
        _message("initialize", request_id=1, params={}),
        _message("initialized", params={}),
        _message("textDocument/didOpen", params={"textDocument": {"uri": uri, "languageId": "lwt", "version": 1, "text": text}}),
        _message("textDocument/documentSymbol", request_id=2, params={"textDocument": {"uri": uri}}),
        _message("textDocument/hover", request_id=3, params={"textDocument": {"uri": uri}, "position": _position(text, "summarize", 4)}),
        _message("textDocument/definition", request_id=4, params={"textDocument": {"uri": uri}, "position": _position(text, "summarize", 4)}),
        _message("textDocument/didChange", params={"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"text": broken_text}]}),
        _message("textDocument/didChange", params={"textDocument": {"uri": uri, "version": 3}, "contentChanges": [{"text": text}]}),
        _message("textDocument/didClose", params={"textDocument": {"uri": uri}}),
        _message("shutdown", request_id=5, params={}),
        _message("exit"),
    ]
    process = subprocess.Popen(
        [sys.executable, "-m", "lwt.lsp_server"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    payload = b"".join(encode_message(item) for item in sequence)
    try:
        stdout, stderr = process.communicate(payload, timeout=12)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=3)
        raise RuntimeError("language server smoke timed out") from None
    if process.returncode != 0:
        raise RuntimeError(f"language server exited with {process.returncode}")
    if b"Traceback" in stderr:
        raise RuntimeError("language server wrote a traceback")
    messages = _decode_frames(stdout)
    by_id = {item["id"]: item for item in messages if "id" in item}
    diagnostics = [item for item in messages if item.get("method") == "textDocument/publishDiagnostics"]
    if [item["id"] for item in by_id.values()] != [1, 2, 3, 4, 5]:
        # IDs are monotonic in this fixed transcript; dict insertion preserves wire order.
        raise RuntimeError("missing or reordered LSP responses")
    capabilities = by_id[1]["result"]["capabilities"]
    if capabilities.get("positionEncoding") != "utf-16":
        raise RuntimeError("server did not negotiate UTF-16 positions")
    symbols = by_id[2]["result"]
    hover = by_id[3]["result"]
    definition = by_id[4]["result"]
    diagnostic_codes = [
        [item["code"] for item in notification["params"]["diagnostics"]]
        for notification in diagnostics
    ]
    if diagnostic_codes != [[], ["STC010"], [], []]:
        raise RuntimeError(f"unexpected diagnostic sequence: {diagnostic_codes}")
    if hover["contents"]["value"] != "fn summarize(batch)":
        raise RuntimeError("hover did not resolve the module function")
    definition_path = Path(definition["uri"].replace("file:///", "", 1))
    if definition_path.name != "stats_utils.lwt":
        # Windows file URI paths need URL parsing; basename is stable after decode.
        from urllib.parse import unquote, urlsplit
        definition_path = Path(unquote(urlsplit(definition["uri"]).path))
    if definition_path.name != "stats_utils.lwt":
        raise RuntimeError("definition did not point to the imported function")
    if by_id[5].get("result", "missing") is not None:
        raise RuntimeError("shutdown must return null")

    report = {
        "schema_version": 1,
        "server": {"name": "lwt-language-server", "version": "0.1"},
        "transcript": [
            "initialize",
            "initialized",
            "didOpen",
            "documentSymbol",
            "hover",
            "definition",
            "didChange(STC010)",
            "didChange(clear)",
            "didClose",
            "shutdown",
            "exit",
        ],
        "capabilities": ["utf-16", "full-sync", "hover", "definition", "documentSymbol"],
        "entry": "examples/modules/main.lwt",
        "symbols": [item["name"] for item in symbols],
        "hover": hover["contents"]["value"],
        "definition": {"uri": "examples/modules/stats_utils.lwt", "line": definition["range"]["start"]["line"], "character": definition["range"]["start"]["character"]},
        "diagnostic_codes_by_publication": diagnostic_codes,
        "response_ids_in_order": [item["id"] for item in messages if "id" in item],
        "stdout_is_lsp_framed": True,
        "stderr_traceback": False,
        "exit_code": process.returncode,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded, encoding="utf-8", newline="\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "lsp-smoke.json")
    args = parser.parse_args(argv)
    try:
        report = run(args.output.resolve())
    except Exception as error:
        print(f"LSP smoke failed: {error}", file=sys.stderr)
        return 1
    print(f"LSP smoke passed: {len(report['transcript'])} protocol steps, {len(report['symbols'])} symbols, diagnostics clear after repair")
    print(f"Evidence: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
