import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = REPO_ROOT / "scripts" / "setup.sh"


class SetupScriptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "scripts").mkdir()
        shutil.copy2(SETUP_SCRIPT, self.root / "scripts" / "setup.sh")
        (self.root / "pyproject.toml").write_text(
            "[project]\nname = \"trainee\"\nversion = \"0.0.0\"\n",
            encoding="utf-8",
        )
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.command_log = self.root / "commands.log"
        self._write_command(
            "uv",
            """\
printf 'uv %s\\n' "$*" >> "$COMMAND_LOG"
if [ "$1" = "venv" ]; then
    mkdir -p .venv/bin
    printf '#!/bin/sh\\nprintf "python %%s\\\\n" "$*" >> "$COMMAND_LOG"\\n' \
        > .venv/bin/python
    chmod +x .venv/bin/python
fi
""",
        )
        self._write_command("uname", "printf 'Darwin\\n'\n")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_command(self, name: str, body: str) -> None:
        path = self.bin_dir / name
        path.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _run_setup(self) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("BUILD_NVIDIA_COM_API_TOKEN", None)
        env["COMMAND_LOG"] = str(self.command_log)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        return subprocess.run(
            ["sh", "scripts/setup.sh"],
            cwd=self.root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_installs_python_dependencies_browser_and_blackhole(self) -> None:
        self._write_command("system_profiler", "exit 1\n")
        self._write_command(
            "brew",
            """\
printf 'brew %s\\n' "$*" >> "$COMMAND_LOG"
if [ "$1" = "list" ]; then
    exit 1
fi
""",
        )

        result = self._run_setup()

        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.command_log.read_text(encoding="utf-8")
        self.assertIn("uv venv --python 3.12 .venv", commands)
        self.assertIn(
            "uv pip install --python .venv/bin/python -e .[audio]", commands
        )
        self.assertIn("python -m playwright install chromium", commands)
        self.assertIn("brew install --cask blackhole-2ch", commands)
        self.assertIn("export BUILD_NVIDIA_COM_API_TOKEN=", result.stdout)
        self.assertIn("Open Audio MIDI Setup", result.stdout)

    def test_reuses_existing_environment_and_blackhole_installation(self) -> None:
        python = self.root / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text(
            '#!/bin/sh\nprintf \'python %s\\n\' "$*" >> "$COMMAND_LOG"\n',
            encoding="utf-8",
        )
        python.chmod(python.stat().st_mode | stat.S_IXUSR)
        self._write_command("system_profiler", "printf 'BlackHole 2ch\\n'\n")

        result = self._run_setup()

        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.command_log.read_text(encoding="utf-8")
        self.assertNotIn("uv venv", commands)
        self.assertIn("Python environment already exists", result.stdout)
        self.assertIn("BlackHole 2ch is already installed", result.stdout)
        self.assertIn("Open Audio MIDI Setup", result.stdout)


if __name__ == "__main__":
    unittest.main()
