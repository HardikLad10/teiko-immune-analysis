"""Guards the exercise's canary. See docs/SPEC.md section 14."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The only treatments that exist in cell-count.csv. Anything else appearing in
# a tracked file means text was copied from the brief without being read.
KNOWN_TREATMENTS = {"miraclib", "phauximab", "none"}

# Matches the naming pattern of the fictional drugs in this exercise.
DRUG_PATTERN = re.compile(r"\b[a-z]{4,}(?:clib|zide|mab|nib|tide|stat)\b")


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [ROOT / line for line in out.stdout.splitlines() if line]


def test_no_unknown_treatment_names_in_repository():
    offenders = {}
    for path in tracked_files():
        if path.name == "cell-count.csv" or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found = {m for m in DRUG_PATTERN.findall(text.lower())} - KNOWN_TREATMENTS
        if found:
            offenders[path.relative_to(ROOT).as_posix()] = sorted(found)
    assert offenders == {}, f"unknown treatment names found: {offenders}"
