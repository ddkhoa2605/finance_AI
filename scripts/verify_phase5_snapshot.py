"""Verify that Phase 5 baseline inputs, outputs, and source files have not drifted."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "reports" / "phase5_artifact_snapshot.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_entry(relative_path: str, expected: dict) -> list[str]:
    path = PROJECT_ROOT / relative_path
    failures = []
    if not path.exists():
        return [f"missing: {relative_path}"]
    actual_hash = sha256(path)
    if actual_hash != expected["sha256"]:
        failures.append(
            f"hash mismatch: {relative_path} expected={expected['sha256']} actual={actual_hash}"
        )
    if path.stat().st_size != int(expected["bytes"]):
        failures.append(
            f"size mismatch: {relative_path} expected={expected['bytes']} actual={path.stat().st_size}"
        )
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
        if len(frame) != int(expected["rows"]):
            failures.append(
                f"row mismatch: {relative_path} expected={expected['rows']} actual={len(frame)}"
            )
        if list(frame.columns) != expected["columns"]:
            failures.append(f"schema mismatch: {relative_path}")
    return failures


def main() -> None:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Phase 5 snapshot manifest not found: {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures = []
    for section in ["strict_artifacts", "source_files"]:
        for relative_path, expected in manifest[section].items():
            failures.extend(verify_entry(relative_path, expected))
    if failures:
        print("PHASE_5_SNAPSHOT=FAIL")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("PHASE_5_SNAPSHOT=PASS")
    print(f"- tag: {manifest['snapshot_tag']}")
    print(f"- champion: {manifest['forecast_summary']['champion']}")
    print(f"- verified files: {len(manifest['strict_artifacts']) + len(manifest['source_files'])}")


if __name__ == "__main__":
    main()
