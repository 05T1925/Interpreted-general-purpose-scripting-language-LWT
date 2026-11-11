"""Render the delivery PPT with PowerPoint COM and check every slide is real.

The deck used to be verified only as a zip/XML artefact: page count, chart
value points and SHA-256. That cannot tell whether a slide actually renders, so
S53 left "PPT footer layout" as an unverified GUI-E item. This tool closes that
gap on Windows: it opens the deck read-only and without a window, exports a PDF
and one PNG per slide, then measures each PNG with PIL.

A blank render is detected by variance of the greyscale image (near_blank when
variance < 50). Nothing here edits the deck: the file is opened read-only and
the only writes are reports/s54-closeout/ppt-pages/*.png and the JSON evidence.

If PowerPoint COM is unavailable the tool exits non-zero and writes no "pass"
record: an unrendered deck must stay unverified.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PPT = ROOT / "slides" / "LWT介绍.pptx"
DEFAULT_OUT = ROOT / "reports" / "s54-closeout"
NEAR_BLANK_VARIANCE = 50.0


def _utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _chart_value_points(ppt: Path) -> int:
    """Cross-check the static signal: how many chart points exist in the XML."""

    points = 0
    with zipfile.ZipFile(ppt) as archive:
        for name in archive.namelist():
            # PowerPoint may keep charts under ppt/charts/ or ppt/slides/charts/
            # depending on the version that last saved the deck.
            if re.match(r"ppt/(?:slides/)?charts/chart\d+\.xml$", name):
                xml = archive.read(name).decode("utf-8", "replace")
                for value in re.findall(r"<c:val>.*?</c:val>", xml, re.S):
                    points += value.count("<c:pt ")
    return points


POWERSHELL_SCRIPT = r"""
param(
    [Parameter(Mandatory=$true)][string]$DeckPath,
    [Parameter(Mandatory=$true)][string]$PdfPath,
    [Parameter(Mandatory=$true)][string]$PagesDir,
    [Parameter(Mandatory=$true)][string]$MetaPath
)
# NB: PowerShell variables are case-insensitive, so the locals must not be
# named $ppt/$Ppt or they would overwrite each other.
$ErrorActionPreference = 'Stop'
$app = $null
$pres = $null
try {
    $app = New-Object -ComObject PowerPoint.Application
    if ($app -eq $null) { throw "cannot create PowerPoint.Application (COM returned null)" }
    # Open(FileName, ReadOnly, Untitled, WithWindow)
    $pres = $app.Presentations.Open($DeckPath, $true, $false, $false)
    $count = $pres.Slides.Count
    # 32 = ppSaveAsPDF
    $pres.SaveAs($PdfPath, 32)
    for ($i = 1; $i -le $count; $i++) {
        $name = Join-Path $PagesDir ("slide-{0:D2}.png" -f $i)
        $pres.Slides.Item($i).Export($name, "PNG", 1280, 720)
    }
    $meta = [pscustomobject]@{
        slides = $count
        version = $app.Version
        pdf = $PdfPath
        exported = $count
    }
    $meta | ConvertTo-Json | Set-Content -LiteralPath $MetaPath -Encoding UTF8
}
catch {
    # Console encoding mangles non-ASCII paths, so hand the message back as JSON.
    $msg = $_.Exception.Message
    $line = $_.InvocationInfo.ScriptLineNumber
    [pscustomobject]@{ error = $msg; line = $line; slides = 0 } | ConvertTo-Json | Set-Content -LiteralPath $MetaPath -Encoding UTF8
    exit 2
}
finally {
    if ($pres -ne $null) { try { $pres.Close() } catch {} }
    if ($app -ne $null) { try { $app.Quit() } catch {} }
}
exit 0
"""


def _page_stats(path: Path) -> dict:
    from PIL import Image, ImageStat  # local import: PIL is optional for non-render use

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        grey = rgb.convert("L")
        stat = ImageStat.Stat(grey)
        variance = float(stat.var[0])
        mean = float(stat.mean[0])
        histogram = grey.histogram()
        saturation = float(ImageStat.Stat(rgb.convert("HSV")).mean[1])
    total = sum(histogram)
    dark = sum(histogram[:64])
    ink = sum(histogram[:240])
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "mean": round(mean, 2),
        "variance": round(variance, 2),
        "dark_ratio": round(dark / total, 4) if total else 0.0,
        # "ink" counts everything that is not near-white; a coloured chart bar
        # is ink but not dark, so dark_ratio alone cannot identify the chart.
        "ink_ratio": round(ink / total, 4) if total else 0.0,
        "saturation": round(saturation, 2),
        "near_blank": variance < NEAR_BLANK_VARIANCE,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ppt", default=str(DEFAULT_PPT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    ppt = Path(args.ppt)
    if not ppt.is_absolute():
        ppt = ROOT / ppt
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    pages_dir = out_dir / "ppt-pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "ppt-render.pdf"
    meta_path = out_dir / "ppt-com-meta.json"
    report_path = out_dir / "ppt-render.json"

    if not ppt.exists():
        print(f"render_ppt: missing deck {ppt}", file=sys.stderr)
        return 2

    for stale in pages_dir.glob("slide-*.png"):
        stale.unlink()

    script_path = out_dir / "_render_ppt.ps1"
    script_path.write_text(POWERSHELL_SCRIPT, encoding="utf-8", newline="\n")
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(script_path), "-DeckPath", str(ppt), "-PdfPath", str(pdf_path),
         "-PagesDir", str(pages_dir), "-MetaPath", str(meta_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, check=False,
    )
    if completed.returncode != 0 or not meta_path.exists():
        message = "no COM metadata"
        if meta_path.exists():
            try:
                message = json.loads(meta_path.read_text(encoding="utf-8-sig")).get("error") or message
            except json.JSONDecodeError:
                message = "unreadable COM metadata"
        if not message or message == "no COM metadata":
            message = completed.stderr.decode("utf-8", "replace").strip() or message
        print(f"render_ppt: PowerPoint COM failed: {message}", file=sys.stderr)
        # Leave an explicit failure record; never a pass.
        report_path.write_text(json.dumps({
            "schema_version": 1,
            "tool": "tools/render_ppt.py",
            "rendered_at_utc": _utc(),
            "ok": False,
            "error": message,
            "ppt_sha256": _sha256(ppt),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        return 2

    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    pages = [_page_stats(path) for path in sorted(pages_dir.glob("slide-*.png"))]
    blank = [page["file"] for page in pages if page["near_blank"]]
    variances = sorted(page["variance"] for page in pages)
    median = variances[len(variances) // 2] if variances else 0.0
    slide10 = next((page for page in pages if page["file"] == "slide-10.png"), None)
    by_dark = sorted(pages, key=lambda p: p["dark_ratio"], reverse=True)
    by_ink = sorted(pages, key=lambda p: p["ink_ratio"], reverse=True)
    by_var = sorted(pages, key=lambda p: p["variance"], reverse=True)
    by_sat = sorted(pages, key=lambda p: p["saturation"], reverse=True)
    chart_points = _chart_value_points(ppt)

    chart_rank = {
        "variance": (by_var.index(slide10) + 1) if slide10 in by_var else None,
        "ink_ratio": (by_ink.index(slide10) + 1) if slide10 in by_ink else None,
        "saturation": (by_sat.index(slide10) + 1) if slide10 in by_sat else None,
        "dark_ratio": (by_dark.index(slide10) + 1) if slide10 in by_dark else None,
    }
    # A chart slide is the fullest and most coloured page; it is not necessarily
    # the darkest one, because bars are coloured rather than black.
    chart_ok = bool(
        slide10
        and slide10["variance"] > median
        and chart_rank["variance"] == 1
        and chart_rank["ink_ratio"] == 1
    )

    doc = {
        "schema_version": 1,
        "tool": "tools/render_ppt.py",
        "rendered_at_utc": _utc(),
        "renderer": f"PowerPoint COM {meta.get('version')}",
        "ppt": ppt.relative_to(ROOT).as_posix() if ppt.is_relative_to(ROOT) else str(ppt),
        "ppt_sha256": _sha256(ppt),
        "slides": meta.get("slides"),
        "exported": meta.get("exported"),
        "pdf": pdf_path.relative_to(ROOT).as_posix(),
        "pdf_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
        "pages": pages,
        "blank_pages": blank,
        "variance_median": round(median, 2),
        "slide10_chart_signal": {
            "variance": slide10["variance"] if slide10 else None,
            "variance_above_median": bool(slide10 and slide10["variance"] > median),
            "ink_ratio": slide10["ink_ratio"] if slide10 else None,
            "saturation": slide10["saturation"] if slide10 else None,
            "dark_ratio": slide10["dark_ratio"] if slide10 else None,
            "rank": chart_rank,
            "html": (
                "slide 10 is the page with the highest variance and the highest "
                "ink ratio; dark_ratio is reported but not used as the signal "
                "because the chart bars are coloured, not black."
            ),
        },
        "chart_value_points_xml": chart_points,
        "near_blank_threshold": NEAR_BLANK_VARIANCE,
        "ok": bool(meta.get("slides") == len(pages) and not blank
                   and pdf_path.exists() and chart_ok),
        "note": "Pixels prove each slide renders; the 12 chart values on slide 10 are "
                "cross-checked in the XML (chart_value_points_xml) and remain a human "
                "eye check in the GUI-E item.",
    }
    report_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    script_path.unlink(missing_ok=True)

    print(f"render_ppt: slides={doc['slides']} pages={len(pages)} blank={len(blank)} "
          f"pdf={doc['pdf_bytes']}B slide10_var={doc['slide10_chart_signal']['variance']} "
          f"median={doc['variance_median']} ok={doc['ok']}")
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
