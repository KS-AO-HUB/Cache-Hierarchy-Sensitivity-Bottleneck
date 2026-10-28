#!/usr/bin/env python3
"""
Plot how N=256 reacts to bigger L2 sizes (O3 runs only).

This expects rows for:
- n256_baseline_l1d32_l2_256
- n256_l1d32_l2_512
- n256_l1d32_l2_1MB
- n256_l1d32_l2_2MB
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


CSV_PATH = Path("/workspace/project/experiments/results_summary_o3.csv")
PLOT_DIR = Path("/workspace/project/experiments/plots")

TAGS = [
    "n256_baseline_l1d32_l2_256",
    "n256_l1d32_l2_512",
    "n256_l1d32_l2_1MB",
    "n256_l1d32_l2_2MB",
]


def l2_size_to_kb(l2: str) -> int:
    s = l2.strip().upper()
    if s.endswith("MB"):
        return int(s.replace("MB", "")) * 1024
    if s.endswith("KB"):
        return int(s.replace("KB", ""))
    raise ValueError(f"Unrecognized L2 size: {l2}")


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    rows_by_tag: dict[str, dict[str, str]] = {}
    with CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            tag = row.get("tag", "")
            if tag in TAGS:
                rows_by_tag[tag] = row

    missing = [t for t in TAGS if t not in rows_by_tag]
    if missing:
        raise RuntimeError(
            "Missing required tags in CSV (re-run summarizer after all runs complete): "
            + ", ".join(missing)
        )

    x_kb = [l2_size_to_kb(rows_by_tag[t]["l2_size"]) for t in TAGS]
    ipc = [float(rows_by_tag[t]["ipc"]) for t in TAGS]
    l2_mpki = [float(rows_by_tag[t]["l2_mpki"]) for t in TAGS]
    sim_s = [float(rows_by_tag[t]["sim_seconds"]) for t in TAGS]

    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax1 = plt.subplots(figsize=(8.2, 5.0))
    ax1.plot(x_kb, ipc, marker="o", linewidth=2, label="IPC")
    ax1.set_xscale("log", base=2)
    ax1.set_xticks(x_kb)
    ax1.set_xticklabels(
        [rows_by_tag[t]["l2_size"] for t in TAGS], rotation=0
    )
    ax1.set_xlabel("L2 size")
    ax1.set_ylabel("IPC")
    ax1.set_title("GEMM N=256: IPC vs L2 (L1D=32kB, O3)")
    ax1.grid(alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(x_kb, l2_mpki, marker="s", linewidth=2, color="#d95f02", label="L2 MPKI")
    ax2.set_ylabel("L2 MPKI")

    lines = ax1.get_lines() + ax2.get_lines()
    labels = [ln.get_label() for ln in lines]
    ax1.legend(lines, labels, loc="center right")
    fig.tight_layout()
    out = PLOT_DIR / "n256_ipc_l2mpki_vs_l2_size.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    ax.plot(x_kb, sim_s, marker="o", linewidth=2, color="#1b9e77")
    ax.set_xscale("log", base=2)
    ax.set_xticks(x_kb)
    ax.set_xticklabels([rows_by_tag[t]["l2_size"] for t in TAGS])
    ax.set_xlabel("L2 size")
    ax.set_ylabel("simSeconds")
    ax.set_title("GEMM N=256: simulated time vs L2 (L1D=32kB, O3)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out2 = PLOT_DIR / "n256_simseconds_vs_l2_size.png"
    fig.savefig(out2, dpi=180)
    plt.close(fig)

    print(f"Wrote {out}")
    print(f"Wrote {out2}")


if __name__ == "__main__":
    main()
