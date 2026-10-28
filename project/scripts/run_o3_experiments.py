#!/usr/bin/env python3
"""
Run gem5 experiments from a manifest, always with O3CPU.

It logs each run, saves basic metadata, and writes one session summary json.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_GEM5_BIN = "/opt/gem5/build/X86/gem5.opt"
DEFAULT_CONFIG_SCRIPT = "/workspace/project/configs/run_experiment.py"
DEFAULT_RESULTS_ROOT = "/workspace/project/results"
DEFAULT_SESSION_LOG_DIR = "/workspace/project/experiments/logs"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_tag(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in text)


@dataclass
class Experiment:
    benchmark: str
    tag: str
    binary: str
    binary_args: str
    l1d_size: str
    l1i_size: str
    l2_size: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run O3-only gem5 experiments.")
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to JSON manifest containing experiment list.",
    )
    parser.add_argument(
        "--gem5_bin",
        default=DEFAULT_GEM5_BIN,
        help=f"Path to gem5 binary (default: {DEFAULT_GEM5_BIN})",
    )
    parser.add_argument(
        "--config_script",
        default=DEFAULT_CONFIG_SCRIPT,
        help=f"Path to run_experiment.py (default: {DEFAULT_CONFIG_SCRIPT})",
    )
    parser.add_argument(
        "--results_root",
        default=DEFAULT_RESULTS_ROOT,
        help=f"Results root directory (default: {DEFAULT_RESULTS_ROOT})",
    )
    parser.add_argument(
        "--session_log_dir",
        default=DEFAULT_SESSION_LOG_DIR,
        help=f"Session log dir (default: {DEFAULT_SESSION_LOG_DIR})",
    )
    parser.add_argument(
        "--continue_on_error",
        action="store_true",
        help="Continue executing remaining experiments when one fails.",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> list[Experiment]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    experiments = payload.get("experiments", [])
    if not experiments:
        raise ValueError("Manifest must include a non-empty 'experiments' list.")

    parsed: list[Experiment] = []
    for idx, item in enumerate(experiments):
        missing = [
            key
            for key in ("benchmark", "tag", "binary")
            if not item.get(key)
        ]
        if missing:
            raise ValueError(
                f"Experiment #{idx} is missing required fields: {', '.join(missing)}"
            )

        parsed.append(
            Experiment(
                benchmark=str(item["benchmark"]),
                tag=str(item["tag"]),
                binary=str(item["binary"]),
                binary_args=str(item.get("binary_args", "")),
                l1d_size=str(item.get("l1d_size", "32kB")),
                l1i_size=str(item.get("l1i_size", "32kB")),
                l2_size=str(item.get("l2_size", "256kB")),
            )
        )
    return parsed


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


def run_one(
    exp: Experiment,
    gem5_bin: Path,
    config_script: Path,
    results_root: Path,
) -> dict[str, Any]:
    outdir = results_root / safe_tag(exp.benchmark) / safe_tag(exp.tag)
    outdir.mkdir(parents=True, exist_ok=True)

    command = [
        str(gem5_bin),
        f"--outdir={outdir}",
        str(config_script),
        "--binary",
        exp.binary,
        "--binary_args",
        exp.binary_args,
        "--cpu_type",
        "O3CPU",
        "--l1d_size",
        exp.l1d_size,
        "--l1i_size",
        exp.l1i_size,
        "--l2_size",
        exp.l2_size,
    ]
    command_pretty = " ".join(shlex.quote(part) for part in command)
    (outdir / "command.sh").write_text(command_pretty + "\n", encoding="utf-8")

    metadata = {
        "benchmark": exp.benchmark,
        "tag": exp.tag,
        "binary": exp.binary,
        "binary_args": exp.binary_args,
        "cpu_type": "O3CPU",
        "l1d_size": exp.l1d_size,
        "l1i_size": exp.l1i_size,
        "l2_size": exp.l2_size,
        "outdir": str(outdir),
    }
    write_json(outdir / "config_used.json", metadata)

    started_at = utc_now_iso()
    start_ts = time.time()
    run_log_path = outdir / "run.log"
    with run_log_path.open("w", encoding="utf-8") as run_log:
        run_log.write(f"[{started_at}] START {command_pretty}\n")
        run_log.flush()
        proc = subprocess.run(
            command,
            stdout=run_log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    end_ts = time.time()
    ended_at = utc_now_iso()

    status = "success" if proc.returncode == 0 else "failed"
    run_record = {
        **metadata,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "duration_seconds": round(end_ts - start_ts, 3),
        "return_code": proc.returncode,
        "status": status,
        "log_file": str(run_log_path),
        "stats_txt": str(outdir / "stats.txt"),
        "stats_json": str(outdir / "stats.json"),
    }
    write_json(outdir / "run_record.json", run_record)
    return run_record


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    gem5_bin = Path(args.gem5_bin).resolve()
    config_script = Path(args.config_script).resolve()
    results_root = Path(args.results_root).resolve()
    session_log_dir = Path(args.session_log_dir).resolve()

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    if not gem5_bin.exists():
        raise FileNotFoundError(f"gem5 binary not found: {gem5_bin}")
    if not config_script.exists():
        raise FileNotFoundError(f"Config script not found: {config_script}")

    experiments = load_manifest(manifest_path)
    session_start = utc_now_iso()
    session_label = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session_id = f"o3_run_{session_label}"

    session_log_dir.mkdir(parents=True, exist_ok=True)
    session_manifest_copy = session_log_dir / f"{session_id}_manifest_snapshot.json"
    session_summary_path = session_log_dir / f"{session_id}_summary.json"

    with manifest_path.open("r", encoding="utf-8") as manifest_handle:
        manifest_payload = json.load(manifest_handle)
    write_json(session_manifest_copy, manifest_payload)

    run_records: list[dict[str, Any]] = []
    failures = 0

    for exp in experiments:
        record = run_one(
            exp=exp,
            gem5_bin=gem5_bin,
            config_script=config_script,
            results_root=results_root,
        )
        run_records.append(record)
        if record["status"] != "success":
            failures += 1
            if not args.continue_on_error:
                break

    session_end = utc_now_iso()
    summary = {
        "session_id": session_id,
        "session_started_at_utc": session_start,
        "session_ended_at_utc": session_end,
        "manifest_path": str(manifest_path),
        "manifest_snapshot_path": str(session_manifest_copy),
        "gem5_bin": str(gem5_bin),
        "config_script": str(config_script),
        "results_root": str(results_root),
        "experiments_requested": len(experiments),
        "experiments_executed": len(run_records),
        "failures": failures,
        "runs": run_records,
    }
    write_json(session_summary_path, summary)

    print("=" * 72)
    print(f"Session ID: {session_id}")
    print(f"Summary:    {session_summary_path}")
    print(f"Runs:       {len(run_records)} executed, {failures} failed")
    print("=" * 72)
    if failures > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
