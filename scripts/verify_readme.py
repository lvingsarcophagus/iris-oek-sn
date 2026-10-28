"""Execute the primary README's actual Bash blocks in an isolated clean clone.

This runs the documented demo and tests, which reset only the Compose demo tables.
Local/CI database passwords are scrubbed from captured command output.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path


def redact(text):
    env = Path(".env")
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(("POSTGRES_PASSWORD=", "HARVESTER_PASSWORD=")):
                text = text.replace(line.split("=", 1)[1], "[REDACTED]")
    return text


def run_block(readme, step):
    match = re.search(rf"### {step}\. .*?```bash\n(.*?)```", readme, flags=re.S)
    if not match:
        raise RuntimeError(f"README step {step} has no runnable Bash block")
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", match.group(1)], capture_output=True, text=True
    )
    output = redact(result.stdout + result.stderr)
    print(output, flush=True)
    if result.returncode:
        raise RuntimeError(f"README step {step} failed with exit code {result.returncode}")
    return output


def get_report(folder):
    paths = list(Path(folder).glob("*/report.json"))
    if len(paths) != 1:
        raise RuntimeError(f"Expected one fresh report under {folder}")
    return paths[0], json.loads(paths[0].read_text())


def main():
    readme = Path("README.md").read_text()
    for name in [
        "app",
        "ui",
        "alembic",
        "assignments",
        "main.py",
        "temp_css.txt",
        "transformer_current.txt",
        "database_facility_pairs.txt",
        "test_overpass_query.txt",
    ]:
        assert not Path(name).exists(), f"Unrelated file remains in clean clone: {name}"
    tracked = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    tracked_env = sorted(name for name in tracked if name and "env" in name.lower())
    assert tracked_env == [".env.example"], tracked_env
    run_block(readme, 2)
    run_block(readme, 3)
    sql_output = run_block(readme, 4)
    first_path, first = get_report("output/fixture-first")
    second_path, second = get_report("output/fixture-second")
    expected = {"received": 12, "accepted": 4, "repaired": 1, "rejected": 7, "duplicate": 1}
    assert first["counts"] == second["counts"] == expected
    assert first["load"] == {"inserted": 4, "updated": 0, "unchanged": 0}
    assert second["load"] == {"inserted": 0, "updated": 0, "unchanged": 4}
    assert first["is_fixture"] and second["is_fixture"]
    test_output = run_block(readme, 5)
    summary = next(line for line in test_output.splitlines() if re.search(r"\b36 passed\b", line))
    assert "skipped" not in summary
    secrets = [
        line.split("=", 1)[1].encode()
        for line in Path(".env").read_text().splitlines()
        if line.startswith(("POSTGRES_PASSWORD=", "HARVESTER_PASSWORD="))
    ]
    patterns = [
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"\bAKIA[A-Z0-9]{16}\b",
        r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    ]
    for name in filter(None, tracked):
        data = Path(name).read_bytes()
        assert not any(secret in data for secret in secrets), f"Local credential in {name}"
        assert not any(re.search(pattern, data.decode(errors="ignore")) for pattern in patterns), (
            name
        )
    evidence = Path("output/review-evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    shutil.copy2(first_path, evidence / "fixture-first-report.json")
    shutil.copy2(second_path, evidence / "fixture-second-report.json")
    (evidence / "fixture-sql-validation.txt").write_text(sql_output)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    clone = {
        "commit": commit,
        "primary_commands": "executed directly from README steps 2–5",
        "test_summary": summary,
        "tracked_env_paths": tracked_env,
        "credential_scan": "passed",
        "root_layout": "assignment-only",
        "fixture_counts": expected,
        "first_load": first["load"],
        "replay": second["load"],
    }
    (evidence / "clean-clone.json").write_text(json.dumps(clone, indent=2) + "\n")
    assert not subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    print(json.dumps(clone, indent=2))


if __name__ == "__main__":
    main()
