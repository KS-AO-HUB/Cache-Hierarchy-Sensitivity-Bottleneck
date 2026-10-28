#!/usr/bin/env python3
"""
Collect O3 gem5 runs into one CSV.

We scan the results tree, keep O3 runs, pull counters from stats.txt,
and write a report-friendly csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_RESULTS_ROOT = "/workspace/project/results"
DEFAULT_OUTPUT_CSV = "/workspace/project/experiments/results_summary_o3.csv"

STATS_PATTERNS = [
    ("sim_seconds", r"^simSeconds\s+([\d.]+)"),
    ("sim_ticks", r"^simTicks\s+(\d+)"),
    ("sim_insts", r"^simInsts\s+(\d+)"),
    ("num_cycles", r"^board\.processor\.cores\.core\.numCycles\s+(\d+)"),
    ("ipc", r"^board\.processor\.cores\.core\.ipc\s+([\d.]+)"),
    ("cpi", r"^board\.processor\.cores\.core\.cpi\s+([\d.]+)"),
    (
        "l1d_misses",
        r"^board\.cache_hierarchy\.l1d-cache-0\.demandMisses::total\s+(\d+)",
    ),
    (
        "l1d_accesses",
        r"^board\.cache_hierarchy\.l1d-cache-0\.demandAccesses::total\s+(\d+)",
    ),
    ("l2_misses", r"^board\.cache_hierarchy\.l2-cache-0\.demandMisses::total\s+(\d+)"),
    (
        "l2_accesses",
        r"^board\.cache_hierarchy\.l2-cache-0\.demandAccesses::total\s+(\d+)",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build O3-only summary CSV.")
    parser.add_argument(
        "--results_root",
        default=DEFAULT_RESULTS_ROOT,
        help=f"Root folder containing experiment outputs (default: {DEFAULT_RESULTS_ROOT})",
    )
    parser.add_argument(
        "--output_csv",
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT_CSV})",
    )
    return parser.parse_args()


def parse_stats_file(stats_path: Path) -> dict[str, str]:
    text = stats_path.read_text(encoding="utf-8", errors="replace")
    result: dict[str, str] = {}
    for name, pattern in STATS_PATTERNS:
        match = re.search(pattern, text, re.MULTILINE)
        result[name] = match.group(1) if match else ""
    return result


def add_derived_metrics(row: dict[str, Any]) -> None:
    def to_int(value: str) -> int:
        return int(value) if value else 0

    sim_insts = to_int(row.get("sim_insts", "0"))
    l1d_misses = to_int(row.get("l1d_misses", "0"))
    l1d_accesses = to_int(row.get("l1d_accesses", "0"))
    l2_misses = to_int(row.get("l2_misses", "0"))
    l2_accesses = to_int(row.get("l2_accesses", "0"))

    if sim_insts > 0:
        row["l1d_mpki"] = f"{(l1d_misses * 1000.0) / sim_insts:.4f}"
        row["l2_mpki"] = f"{(l2_misses * 1000.0) / sim_insts:.4f}"
    else:
        row["l1d_mpki"] = ""
        row["l2_mpki"] = ""

    row["l1d_miss_rate"] = (
        f"{l1d_misses / l1d_accesses:.6f}" if l1d_accesses > 0 else ""
    )
    row["l2_miss_rate"] = f"{l2_misses / l2_accesses:.6f}" if l2_accesses > 0 else ""


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def infer_from_path(outdir: Path, results_root: Path) -> dict[str, str]:
    rel_parts = outdir.relative_to(results_root).parts
    benchmark = rel_parts[0] if len(rel_parts) >= 1 else ""
    tag = rel_parts[1] if len(rel_parts) >= 2 else outdir.name
    return {"benchmark": benchmark, "tag": tag}


def collect_rows(results_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_outdirs: set[Path] = set()

    for config_path in sorted(results_root.rglob("config_used.json")):
        config = load_config(config_path)
        if config.get("cpu_type") != "O3CPU":
            continue

        outdir = config_path.parent
        seen_outdirs.add(outdir)
        stats_path = outdir / "stats.txt"
        run_record_path = outdir / "run_record.json"
        if not stats_path.exists():
            continue

        parsed = parse_stats_file(stats_path)
        row = {
            "benchmark": config.get("benchmark", ""),
            "tag": config.get("tag", ""),
            "cpu_type": config.get("cpu_type", ""),
            "binary": config.get("binary", ""),
            "binary_args": config.get("binary_args", ""),
            "l1d_size": config.get("l1d_size", ""),
            "l1i_size": config.get("l1i_size", ""),
            "l2_size": config.get("l2_size", ""),
            "outdir": str(outdir),
            "run_status": "",
            "duration_seconds": "",
        }
        if run_record_path.exists():
            run_record = load_config(run_record_path)
            row["run_status"] = run_record.get("status", "")
            row["duration_seconds"] = run_record.get("duration_seconds", "")

        row.update(parsed)
        add_derived_metrics(row)
        rows.append(row)

    # Fallback for older runs without config_used.json.
    # Still only keep outputs clearly marked as O3.
    for stats_path in sorted(results_root.rglob("stats.txt")):
        outdir = stats_path.parent
        if outdir in seen_outdirs:
            continue
        if "cpu_O3CPU" not in str(outdir):
            continue

        inferred = infer_from_path(outdir, results_root)
        row = {
            "benchmark": inferred["benchmark"],
            "tag": inferred["tag"],
            "cpu_type": "O3CPU",
            "binary": "",
            "binary_args": "",
            "l1d_size": "",
            "l1i_size": "",
            "l2_size": "",
            "outdir": str(outdir),
            "run_status": "legacy",
            "duration_seconds": "",
        }
        row.update(parse_stats_file(stats_path))
        add_derived_metrics(row)
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("No O3CPU results found. Nothing to write.")
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    results_root = Path(args.results_root).resolve()
    output_csv = Path(args.output_csv).resolve()

    if not results_root.exists():
        raise FileNotFoundError(f"Results root not found: {results_root}")

    rows = collect_rows(results_root)
    write_csv(output_csv, rows)
    print(f"Wrote {len(rows)} O3-only rows to {output_csv}")


if __name__ == "__main__":
    main()
