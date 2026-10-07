"""CLI-level PermissionError mapping test without changing host permissions."""

from __future__ import annotations

from io import BytesIO, StringIO, TextIOWrapper
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from lwt.cli import main


class ReconfigurableCapture(StringIO):
    def reconfigure(self, **_kwargs: object) -> None:
        pass


class ReadTextPermissionErrorTests(unittest.TestCase):
    def test_permission_error_has_runtime_diagnostic_and_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "permission.lwt"
            blocked = root / "blocked.txt"
            blocked.write_text("not actually protected", encoding="utf-8")
            source.write_text(f'emit read_text("{blocked.as_posix()}");', encoding="utf-8")
            source_argument = str(source)

            stdout = ReconfigurableCapture()
            stderr = ReconfigurableCapture()
            stdin = TextIOWrapper(BytesIO())
            actual_read_bytes = Path.read_bytes

            def injected_read_bytes(path: Path) -> bytes:
                if path.resolve() == blocked.resolve():
                    raise PermissionError("deterministic injected denial")
                return actual_read_bytes(path)

            try:
                with (
                    patch.object(sys, "stdout", stdout),
                    patch.object(sys, "stderr", stderr),
                    patch.object(sys, "stdin", stdin),
                    patch.object(Path, "read_bytes", injected_read_bytes),
                ):
                    exit_code = main([source_argument])
            finally:
                stdin.close()

        self.assertEqual(exit_code, 3)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(),
            f"{source_argument}:1:6: RuntimeError: could not read text file\n",
        )
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
