"""Run a prompt from prompts/ over a JSONL file with the Claude Code CLI (`claude -p`, no API key).

The input is sent in batches, so a long run never sends one huge request; the answers of
all batches are written to one JSONL file for the module's import step.
"""

import re
import subprocess
from pathlib import Path

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def enterprise_number(value):
    """KBO format (0800.000.004) for a number in an answer; Claude sometimes drops the dots or adds BE."""
    digits = re.sub(r"\D", "", str(value))
    return f"{digits[:4]}.{digits[4:7]}.{digits[7:]}" if len(digits) == 10 else value


def run(prompt, in_path, out_path, tools=(), model="haiku", batch=10, timeout=1800):
    """Returns the number of input lines sent. Raises CalledProcessError when claude fails (e.g. not logged in)."""
    lines = [line for line in Path(in_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    cmd = ["claude", "-p", "--model", model, (PROMPTS / prompt).read_text(encoding="utf-8")]
    if tools:
        cmd[2:2] = ["--allowedTools", " ".join(tools)]
    with open(out_path, "w", encoding="utf-8") as out:
        for i in range(0, len(lines), batch):
            r = subprocess.run(cmd, input="\n".join(lines[i:i + batch]) + "\n", capture_output=True, text=True,
                               timeout=timeout, check=False)
            if r.returncode:
                raise subprocess.CalledProcessError(r.returncode, "claude -p", r.stdout + r.stderr)
            out.write(r.stdout.rstrip("\n") + "\n")
    return len(lines)
