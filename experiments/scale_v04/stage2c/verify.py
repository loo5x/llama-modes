"""Verify native identity, oracle repeats, and Stage 2c artifact hashes."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    checks = []
    identity = json.loads((ROOT.parent / "stage2b/identity.json").read_text())
    for item in identity["runtime_files"]:
        path = Path(item["path"])
        checks.append({"path": str(path), "sha256": sha(path), "expected": item["sha256"]})
    model = identity["model"]
    checks.append({"path": model["path"], "sha256": sha(Path(model["path"])), "expected": model["sha256"]})
    assert all(x["sha256"] == x["expected"] for x in checks)
    oracle_checks = []
    for case in ["objective_2", "paraphrase_2", "city_control"]:
        old = json.loads((ROOT.parent / f"stage2b/oracle-default-with-control/{case}-original-scores.json").read_text())
        a = json.loads((ROOT / f"oracle-confirmation/{case}-original-scores.json").read_text())
        b = json.loads((ROOT / f"oracle-confirmation/{case}-reverse-scores.json").read_text())
        oracle_checks.append({"case": case, "exact_old_and_reversed_agreement": old == a == b[::-1]})
    assert all(x["exact_old_and_reversed_agreement"] for x in oracle_checks)
    diff = subprocess.check_output(["git", "diff", "--name-only"], text=True)
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True)
    assert not diff and not staged
    data = {"identity_checks": checks, "oracle_checks": oracle_checks, "tracked_diff": diff, "staged_diff": staged}
    (ROOT / "verification.json").write_text(json.dumps(data, indent=2) + "\n")
    manifest = [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha(p)}
                for p in sorted(ROOT.rglob("*")) if p.is_file() and p.name != "manifest.json" and "__pycache__" not in p.parts]
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Verified identities:", len(checks), "oracle cases:", len(oracle_checks), "artifacts:", len(manifest))


if __name__ == "__main__":
    main()
