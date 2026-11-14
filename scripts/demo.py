"""Capture a real CLI session in a temporary copy of the sample repository."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    work = repository / ".demo-work"
    work.mkdir(exist_ok=True)
    transcript: list[str] = []
    with tempfile.TemporaryDirectory(dir=work) as temporary:
        project = Path(temporary) / "project"
        shutil.copytree(repository / "examples" / "monorepo", project)
        commands = [
            ["--agent", "all", "--dry-run"],
            ["--agent", "all", "--diff"],
            ["--agent", "all"],
            ["--agent", "all", "--update"],
            ["--agent", "all"],
        ]
        for arguments, expected_exit in zip(commands, [0, 0, 0, 0, 0], strict=True):
            transcript.append("$ python generate_rules.py project " + " ".join(arguments))
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(repository / "generate_rules.py"),
                    str(project),
                    *arguments,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            if result.returncode != expected_exit:
                raise RuntimeError(f"Unexpected demo exit: {result.returncode}: {result.stderr}")
            transcript.extend(
                [result.stdout.rstrip(), result.stderr.rstrip(), f"[exit {result.returncode}]", ""]
            )
        samples = repository / "docs" / "samples"
        samples.mkdir(parents=True, exist_ok=True)
        for name in ["AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md"]:
            shutil.copyfile(project / name, samples / Path(name).name)
    (repository / "docs" / "demo.txt").write_text(
        "\n".join(transcript), encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
