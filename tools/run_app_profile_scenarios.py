"""Run and verify two fixed log-analyser profile demonstrations."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lwt.profile_schema import load_profile_json


SOURCE = "app/log_report.lwt"
SAMPLE = "app/fixtures/sample.log"
DEFAULT_EXPECTED = (REPO_ROOT / "app/fixtures/sample.expected.txt").read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
FILTERED_EXPECTED = (
    b"LWT log report\n"
    b"Total lines: 7\n"
    b"Valid records: 6\n"
    b"Malformed lines: 1\n"
    b"Matched records: 1\n"
    b"Level counts:\n"
    b"WARN|1\n"
    b"Top modules:\n"
    b"cache|1\n"
    b"Matching examples (first 3):\n"
    b"2026-10-07T10:00:03Z|WARN|cache|retry scheduled\n"
)


def _run(arguments: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "lwt", *arguments],
        cwd=REPO_ROOT,
        input=b"",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
        timeout=20,
    )


def _verify_pair(label: str, application_args: list[str], expected: bytes, profile_path: Path) -> dict[str, object]:
    normal = _run([SOURCE, "--", *application_args])
    profiled = _run(["--profile", str(profile_path), SOURCE, "--", *application_args])
    if (normal.returncode, normal.stdout, normal.stderr) != (0, expected, b""):
        raise RuntimeError(f"{label}: non-profile CLI output does not match the fixed application contract")
    if (profiled.returncode, profiled.stdout, profiled.stderr) != (normal.returncode, normal.stdout, normal.stderr):
        raise RuntimeError(f"{label}: profile mode changed stdout, stderr, or exit code")
    profile = load_profile_json(profile_path.read_text(encoding="utf-8"))
    if profile["status"] != "success" or profile["exit_code"] != 0:
        raise RuntimeError(f"{label}: profile status is not success")
    print(f"{label}: exit=0 stdout_bytes={len(profiled.stdout)} stderr_bytes=0 modules={len(profile['modules'])} statements={profile['coverage']['summary']['statements']['covered']}/{profile['coverage']['summary']['statements']['total']} functions={profile['coverage']['summary']['functions']['covered']}/{profile['coverage']['summary']['functions']['total']} decisions={profile['coverage']['summary']['decisions']['covered']}/{profile['coverage']['summary']['decisions']['total']}")
    return profile


def main() -> int:
    reports = REPO_ROOT / "reports"
    reports.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="lwt-app-profile-") as temporary:
            temp = Path(temporary)
            profiles = [
                _verify_pair("default", [SAMPLE], DEFAULT_EXPECTED, temp / "default.json"),
                _verify_pair(
                    "warn-retry-top2",
                    [SAMPLE, "--level", "WARN", "--keyword", "retry", "--top", "2"],
                    FILTERED_EXPECTED,
                    temp / "filtered.json",
                ),
            ]
            # Use the public merger to perform static-definition and hash checks.
            for index, profile in enumerate(profiles, 1):
                temp_path = temp / f"input-{index}.json"
                temp_path.write_text(json.dumps(profile, ensure_ascii=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
            merged_path = reports / "app-lwt-profile.json"
            merge = subprocess.run(
                [sys.executable, "tools/merge_lwt_profiles.py", str(temp / "input-1.json"), str(temp / "input-2.json"), "--output", str(merged_path)],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                check=False,
                timeout=20,
            )
            if merge.returncode != 0:
                raise RuntimeError(merge.stderr.decode("utf-8", errors="replace").strip())
            rendered = subprocess.run(
                [sys.executable, "tools/render_lwt_profile.py", str(merged_path), "--output", str(reports / "app-lwt-profile.html")],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                check=False,
                timeout=20,
            )
            if rendered.returncode != 0:
                raise RuntimeError(rendered.stderr.decode("utf-8", errors="replace").strip())
            final_profile = load_profile_json(merged_path.read_text(encoding="utf-8"))
            print(f"merged: runs={len(final_profile['runs'])} events_kept_separate=yes json_bytes={merged_path.stat().st_size} html_bytes={(reports / 'app-lwt-profile.html').stat().st_size}")
    except subprocess.TimeoutExpired:
        print("app profile demo failed: a CLI tool exceeded the 20-second timeout", file=sys.stderr)
        return 1
    except (OSError, UnicodeError, RuntimeError, ValueError) as error:
        print(f"app profile demo failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
