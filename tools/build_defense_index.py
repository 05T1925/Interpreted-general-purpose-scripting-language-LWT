"""Build the offline defense evidence console (``docs/defense-index.html``).

S49 changes over the S48 hand-written page:

* the 21-slide runbook becomes navigable: each slide has a ``#page-N`` anchor and
  links to the claims it defends;
* every claim row carries ``id="claim-<id>"`` so a runbook row can deep-link to
  it (``defense-index.html#claim-blind``);
* commands are rendered with POSIX quoting (``shlex.join``) so ``python -c`` rows
  are copy-pasteable instead of ``python -c import json;...``;
* statuses come from the last ``reports/s48-defense/defense-probe.json`` run and
  anything not present stays ``UNRUN`` — the page never invents a PASS.

S56.1: the page had stopped showing any status while its footer still quoted the
S49 probe file, so a claim that had turned red (``fresh-clone``) looked fine. Each
claim row now shows the *recorded* status and ``recorded_at_utc`` from the newest
probe record (``reports/s56-hotfix/`` first), labelled as a record, not a live run.

Single file, no CDN, no external font, no network: it must open from a USB stick.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "docs" / "defense-claims.json"
PAGES = ROOT / "docs" / "defense-pages.json"
# A static PASS from a past run is exactly what the defense must not rely on, so
# the console shows the recorded status together with the record's path and
# timestamp; the live exit code on site still decides.
OUT = ROOT / "docs" / "defense-index.html"
PROBE_CANDIDATES = (
    ROOT / "reports" / "s56-hotfix" / "defense-probe.json",
    ROOT / "reports" / "s53-mutation" / "defense-probe.json",
    ROOT / "reports" / "s50-closeout" / "defense-probe-merge.json",
    ROOT / "reports" / "s49-rehearsal" / "defense-probe.json",
    ROOT / "reports" / "s48-defense" / "defense-probe.json",
)

STYLE = """
:root { color-scheme: light dark; --bg:#fff; --fg:#1b1b1b; --muted:#5b6570; --line:#d8dee4; --pass:#1a7f37; --fail:#b42318; --chip:#eef2f6; }
@media (prefers-color-scheme: dark) { :root { --bg:#14181d; --fg:#e6edf3; --muted:#9aa7b2; --line:#2b333c; --pass:#3fb950; --fail:#f85149; --chip:#1d242c; } }
body { margin:0; padding:24px; background:var(--bg); color:var(--fg); font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
h1 { font-size:22px; margin:0 0 6px; }
h2 { font-size:16px; margin:26px 0 8px; }
p.lead { color:var(--muted); margin:0 0 16px; }
.bar { display:flex; gap:10px; align-items:center; margin:0 0 14px; flex-wrap:wrap; }
input[type=search] { padding:8px 10px; border:1px solid var(--line); border-radius:8px; background:transparent; color:var(--fg); min-width:260px; }
.chip { padding:4px 9px; border-radius:999px; background:var(--chip); color:var(--muted); font-size:12px; }
nav.pages { display:flex; gap:6px; flex-wrap:wrap; margin:0 0 8px; }
nav.pages a { display:inline-block; padding:3px 8px; border:1px solid var(--line); border-radius:6px; text-decoration:none; color:var(--fg); font-size:12px; }
nav.pages a.live { border-color:var(--pass); }
table { border-collapse:collapse; width:100%; }
th,td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-size:12px; color:var(--muted); font-weight:600; }
tr.area td { background:var(--chip); font-weight:600; }
code { font:12px/1.45 ui-monospace,Consolas,monospace; word-break:break-all; }
code.cmd { display:inline-block; max-width:640px; }
button { margin-left:6px; padding:2px 8px; border:1px solid var(--line); border-radius:6px; background:transparent; color:var(--muted); cursor:pointer; font-size:11px; }
td.status { font-weight:700; }
tr.pass td.status { color:var(--pass); }
tr.fail td.status { color:var(--fail); }
tr.unrun td.status { color:var(--muted); }
footer { margin-top:20px; color:var(--muted); font-size:12px; }
"""

SCRIPT = """
function copyCmd(btn) {
  const text = btn.parentElement.querySelector('code').innerText;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => { btn.textContent = '已复制'; setTimeout(() => btn.textContent = '复制', 1200); });
  } else {
    const r = document.createRange(); r.selectNode(btn.parentElement.querySelector('code'));
    window.getSelection().removeAllRanges(); window.getSelection().addRange(r);
    document.execCommand('copy'); btn.textContent = '已复制'; setTimeout(() => btn.textContent = '复制', 1200);
  }
}
function filterRows() {
  const q = document.getElementById('q').value.toLowerCase();
  for (const row of document.querySelectorAll('#t tbody tr')) {
    if (row.classList.contains('area')) continue;
    row.style.display = row.innerText.toLowerCase().includes(q) ? '' : 'none';
  }
}
"""


def _cmd_text(command: list[str]) -> str:
    # Prefer a readable, copy-pasteable form for ``python -c``: the snippets are
    # full of single quotes, so shlex's '"'"' escaping is unreadable even though
    # it is correct. Use double quotes when the snippet has no double quote.
    if len(command) == 3 and command[1] == "-c":
        code = command[2]
        if "'" in code and '"' not in code:
            return f'{command[0]} -c "{code}"'
    return shlex.join(command)


def _probe_record() -> tuple[str | None, str, dict[str, dict]]:
    """Return (record path, generated_at_utc, rows by claim id) of the newest probe."""

    path = next((item for item in PROBE_CANDIDATES if item.exists()), None)
    if path is None:
        return None, "", {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in doc.get("results", [])}
    return path.relative_to(ROOT).as_posix(), doc.get("generated_at_utc", ""), rows



def render() -> str:
    claims_doc = json.loads(CLAIMS.read_text(encoding="utf-8"))
    pages_doc = json.loads(PAGES.read_text(encoding="utf-8"))
    claims = claims_doc["claims"]
    pages = pages_doc["pages"]
    # Page -> claim ids, and claim -> page numbers, from the single mapping file.
    page_of: dict[str, list[int]] = {}
    for page in pages:
        for cid in page["claims"]:
            page_of.setdefault(cid, []).append(page["page"])

    live_pages = [p["page"] for p in pages if p["mode"] == "live"]
    probe_path, probe_time, probe_rows = _probe_record()

    out: list[str] = []
    out.append("<!DOCTYPE html>")
    out.append('<html lang="zh-CN">')
    out.append("<head>")
    out.append('<meta charset="utf-8">')
    out.append("<title>LWT 现场可质询证据台</title>")
    out.append(f"<style>{STYLE}</style>")
    out.append("</head>")
    out.append("<body>")
    out.append("<h1>LWT 现场可质询证据台</h1>")
    out.append(
        '<p class="lead">老师随机点一条断言，或按 PPT 页码跳到该页对应的断言，'
        "现场运行命令并对照退出码与输出。所有命令在仓库根执行；离线可用，"
        "无 CDN、无网络依赖。</p>"
    )
    out.append('<div class="bar">')
    out.append('<input type="search" id="q" placeholder="过滤：断言 / 命令 / 证据路径" oninput="filterRows()">')
    out.append(f'<span class="chip">断言 {len(claims)} 条</span>')
    out.append(f'<span class="chip">讲稿 {len(pages)} 页</span>')
    out.append('<span class="chip">“记录状态”是探针历史记录，不是现场结果；现场以真实退出码为准</span>')
    out.append("</div>")

    out.append('<h2 id="pages">按 PPT 页码导航（绿框 = 现场必须跑）</h2>')
    out.append('<nav class="pages">')
    for page in pages:
        cls = ' class="live"' if page["mode"] == "live" else ""
        out.append(
            f'<a href="#page-{page["page"]}"{cls}>P{page["page"]}</a>'
        )
    out.append("</nav>")
    out.append("<table><thead><tr><th>页</th><th>标题</th><th>模式</th><th>对应断言</th></tr></thead><tbody>")
    for page in pages:
        links = " ".join(
            f'<a href="#claim-{html.escape(cid)}"><code>{html.escape(cid)}</code></a>'
            for cid in page["claims"]
        )
        mode = {"live": "现场跑", "recorded": "只展示", "talk": "口播"}[page["mode"]]
        out.append(
            f'<tr id="page-{page["page"]}"><td>{page["page"]}</td>'
            f'<td>{html.escape(page["title"])}</td><td>{mode}</td><td>{links}</td></tr>'
        )
    out.append("</tbody></table>")

    out.append('<h2 id="claims">断言清单</h2>')
    out.append("<table id=\"t\"><thead><tr><th>id</th><th>断言</th><th>现场命令</th><th>证据</th><th>PPT 页</th><th>记录状态（非现场）</th></tr></thead><tbody>")
    current_area = None
    for claim in claims:
        if claim["area"] != current_area:
            current_area = claim["area"]
            out.append(f'<tr class="area"><td colspan="6">{html.escape(current_area)}</td></tr>')
        command = html.escape(_cmd_text(claim["command"]))
        evidence = html.escape(claim["evidence_path"])
        pages_txt = ", ".join(f"P{p}" for p in sorted(page_of.get(claim["id"], []))) or "—"
        heavy = " · heavy" if claim.get("heavy") else ""
        row = probe_rows.get(claim["id"])
        recorded = row.get("status", "UNRUN") if row else "UNRUN"
        css = {"PASS": "pass", "FAIL": "fail", "TIMEOUT": "fail"}.get(recorded, "unrun")
        when = html.escape(row.get("recorded_at_utc", "")) if row else "本记录未含此条"
        out.append(
            f'<tr id="claim-{html.escape(claim["id"])}" class="{css}">'
            f'<td><code>{html.escape(claim["id"])}</code></td>'
            f'<td>{html.escape(claim["claim"])}{heavy}</td>'
            f'<td><code class="cmd">{command}</code><button onclick="copyCmd(this)">复制</button></td>'
            f'<td><a href="{evidence}">{evidence}</a></td>'
            f'<td>{pages_txt}</td>'
            f'<td class="status">{html.escape(recorded)}<br><small>{when}</small></td></tr>'
        )
    out.append("</tbody></table>")

    out.append(
        "<footer>“记录状态”列来自探针记录 "
        f"<code>{html.escape(probe_path or '（无）')}</code>（生成于 {html.escape(probe_time or '—')}，"
        "由 <code>tools/run_defense_probe.py</code> 生成）；它是历史记录，不是现场结果，"
        "现场执行命令后以真实退出码为准。"
        "由 <code>tools/build_defense_index.py</code> 从 <code>docs/defense-claims.json</code> 与 "
        "<code>docs/defense-pages.json</code> 生成。"
        f"现场跑：P{live_pages[0]}–P{live_pages[-1]} 中绿框页。</footer>"
    )
    out.append(f"<script>{SCRIPT}</script>")
    out.append("</body></html>")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--check", action="store_true", help="exit 1 when the file is stale")
    args = parser.parse_args(argv)
    text = render()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current != text:
            print(f"build_defense_index: stale {out.relative_to(ROOT)}")
            return 1
        print("build_defense_index: up to date")
        return 0
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"build_defense_index: {len(text)} bytes -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
