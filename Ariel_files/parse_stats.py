#!/usr/bin/env python3
"""
Parses gem5 stats.txt files from results/ into a single CSV.
Uses the exact stat names from gem5 v24 stdlib output.
"""

import csv
import re
import json
import os

RESULTS_DIR = "/workspace/project/results"
OUTPUT_CSV = "/workspace/project/results_summary.csv"

# (csv_column_name, regex pattern to match in stats.txt)
# We only grab the FIRST match (to avoid the duplicate stats block)
STATS_PATTERNS = [
    ("sim_seconds", r"^simSeconds\s+([\d.]+)"),
    ("sim_ticks", r"^simTicks\s+(\d+)"),
    ("sim_insts", r"^simInsts\s+(\d+)"),
    ("sim_ops", r"^simOps\s+(\d+)"),
    ("num_cycles", r"^board\.processor\.cores\.core\.numCycles\s+(\d+)"),
    ("ipc", r"^board\.processor\.cores\.core\.ipc\s+([\d.]+)"),
    ("cpi", r"^board\.processor\.cores\.core\.cpi\s+([\d.]+)"),
    ("l1d_hits", r"^board\.cache_hierarchy\.l1d-cache-0\.demandHits::total\s+(\d+)"),
    (
        "l1d_misses",
        r"^board\.cache_hierarchy\.l1d-cache-0\.demandMisses::total\s+(\d+)",
    ),
    (
        "l1d_accesses",
        r"^board\.cache_hierarchy\.l1d-cache-0\.demandAccesses::total\s+(\d+)",
    ),
    (
        "l1i_misses",
        r"^board\.cache_hierarchy\.l1i-cache-0\.demandMisses::total\s+(\d+)",
    ),
    (
        "l1i_accesses",
        r"^board\.cache_hierarchy\.l1i-cache-0\.demandAccesses::total\s+(\d+)",
    ),
    ("l2_hits", r"^board\.cache_hierarchy\.l2-cache-0\.demandHits::total\s+(\d+)"),
    ("l2_misses", r"^board\.cache_hierarchy\.l2-cache-0\.demandMisses::total\s+(\d+)"),
    (
        "l2_accesses",
        r"^board\.cache_hierarchy\.l2-cache-0\.demandAccesses::total\s+(\d+)",
    ),
]


def parse_one_stats_file(stats_path):
    """Extract stats from a single stats.txt file."""
    with open(stats_path, "r") as f:
        text = f.read()

    result = {}
    for name, pattern in STATS_PATTERNS:
        match = re.search(pattern, text, re.MULTILINE)
        result[name] = match.group(1) if match else "N/A"

    # --- Derived metrics ---
    try:
        insts = int(result["sim_insts"])
        if insts > 0:
            if result["l1d_misses"] != "N/A":
                result["l1d_mpki"] = f"{int(result['l1d_misses']) * 1000 / insts:.4f}"
            if result["l2_misses"] != "N/A":
                result["l2_mpki"] = f"{int(result['l2_misses']) * 1000 / insts:.4f}"
            if result["l1d_accesses"] != "N/A" and int(result["l1d_accesses"]) > 0:
                result["l1d_miss_rate"] = (
                    f"{int(result['l1d_misses']) / int(result['l1d_accesses']):.6f}"
                )
            if result["l2_accesses"] != "N/A" and int(result["l2_accesses"]) > 0:
                result["l2_miss_rate"] = (
                    f"{int(result['l2_misses']) / int(result['l2_accesses']):.6f}"
                )
        else:
            result["l1d_mpki"] = "N/A"
            result["l2_mpki"] = "N/A"
            result["l1d_miss_rate"] = "N/A"
            result["l2_miss_rate"] = "N/A"
    except (ValueError, ZeroDivisionError):
        result["l1d_mpki"] = "N/A"
        result["l2_mpki"] = "N/A"
        result["l1d_miss_rate"] = "N/A"
        result["l2_miss_rate"] = "N/A"

    return result


def parse_all():
    rows = []

    for root, dirs, files in sorted(os.walk(RESULTS_DIR)):
        if "stats.txt" not in files:
            continue

        # Figure out benchmark name and tag from path
        # Expected: results/<benchmark>/<tag>/stats.txt
        rel = os.path.relpath(root, RESULTS_DIR)
        parts = rel.split(os.sep)
        if len(parts) < 2:
            continue

        benchmark = parts[0]
        tag = parts[1]

        stats_path = os.path.join(root, "stats.txt")
        stats = parse_one_stats_file(stats_path)

        # Load config if available
        config_path = os.path.join(root, "config_used.json")
        config = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)

        row = {
            "benchmark": benchmark,
            "tag": tag,
            "cpu_type": config.get("cpu_type", "unknown"),
            "l1d_size": config.get("l1d_size", "unknown"),
            "l1i_size": config.get("l1i_size", "unknown"),
            "l2_size": config.get("l2_size", "unknown"),
        }
        row.update(stats)
        rows.append(row)

    if not rows:
        print("❌ No stats files found!")
        return

    # Write CSV
    fieldnames = list(rows[0].keys())
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Wrote {len(rows)} rows to {OUTPUT_CSV}")

    # Print a quick summary table
    print(
        f"\n{'Benchmark':<18} {'Tag':<28} {'IPC':<8} {'CPI':<8} {'L1D MPKI':<10} {'L2 MPKI':<10}"
    )
    print("-" * 90)
    for row in rows:
        print(
            f"{row['benchmark']:<18} {row['tag']:<28} {row['ipc']:<8} {row['cpi']:<8} {row.get('l1d_mpki','N/A'):<10} {row.get('l2_mpki','N/A'):<10}"
        )


if __name__ == "__main__":
    parse_all()
