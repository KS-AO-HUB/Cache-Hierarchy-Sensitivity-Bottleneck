#!/usr/bin/env python3
"""
Make plots from the 10-run O3 GEMM sweep.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


CSV_PATH = Path("/workspace/project/experiments/results_summary_o3.csv")
PLOT_DIR = Path("/workspace/project/experiments/plots")


def size_to_kb(size: str) -> int:
    s = size.strip().upper()
    if s.endswith("MB"):
        return int(s.replace("MB", "")) * 1024
    if s.endswith("KB"):
        return int(s.replace("KB", ""))
    return int(s)


def parse_n(binary_args: str) -> int:
    if not isinstance(binary_args, str) or not binary_args.strip():
        return -1
    first = binary_args.strip().split()[0]
    try:
        return int(first)
    except ValueError:
        return -1


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("tag", "").startswith("n"):
                rows.append(row)

    if not rows:
        raise RuntimeError("No 10-run rows found (tags starting with 'n').")

    # L1 sweep with N=128 and L2 fixed at 256kB
    l1_rows = [
        row
        for row in rows
        if row.get("binary_args") == "128 ijk"
        and row.get("l2_size") == "256kB"
        and row.get("l1d_size") in {"16kB", "32kB", "64kB"}
    ]
    l1_rows.sort(key=lambda r: size_to_kb(r["l1d_size"]))
    l1_kb = [size_to_kb(r["l1d_size"]) for r in l1_rows]
    l1_ipc = [float(r["ipc"]) for r in l1_rows]
    l1_mpki = [float(r["l1d_mpki"]) for r in l1_rows]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(l1_kb, l1_ipc, marker="o", linewidth=2)
    ax.set_xticks([16, 32, 64])
    ax.set_xticklabels(["16kB", "32kB", "64kB"])
    ax.set_xlabel("L1D size")
    ax.set_ylabel("IPC")
    ax.set_title("GEMM N=128: IPC vs L1D size (L2=256kB, O3)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "ipc_vs_l1d_n128.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(l1_kb, l1_mpki, marker="o", linewidth=2, color="#d95f02")
    ax.set_xticks([16, 32, 64])
    ax.set_xticklabels(["16kB", "32kB", "64kB"])
    ax.set_xlabel("L1D size")
    ax.set_ylabel("L1D MPKI")
    ax.set_title("GEMM N=128: L1D MPKI vs L1D size (L2=256kB, O3)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "l1d_mpki_vs_l1d_n128.png", dpi=180)
    plt.close(fig)

    # L2 sweep with N=128 and L1D fixed at 32kB
    l2_rows = [
        row
        for row in rows
        if row.get("binary_args") == "128 ijk"
        and row.get("l1d_size") == "32kB"
        and row.get("l2_size") in {"128kB", "256kB", "512kB", "1MB"}
    ]
    l2_rows.sort(key=lambda r: size_to_kb(r["l2_size"]))
    l2_kb = [size_to_kb(r["l2_size"]) for r in l2_rows]
    l2_ipc = [float(r["ipc"]) for r in l2_rows]
    l2_mpki = [float(r["l2_mpki"]) for r in l2_rows]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(l2_kb, l2_ipc, marker="o", linewidth=2)
    ax.set_xscale("log", base=2)
    ax.set_xticks([128, 256, 512, 1024])
    ax.set_xticklabels(["128kB", "256kB", "512kB", "1MB"])
    ax.set_xlabel("L2 size")
    ax.set_ylabel("IPC")
    ax.set_title("GEMM N=128: IPC vs L2 size (L1D=32kB, O3)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "ipc_vs_l2_n128.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(l2_kb, l2_mpki, marker="o", linewidth=2, color="#7570b3")
    ax.set_xscale("log", base=2)
    ax.set_xticks([128, 256, 512, 1024])
    ax.set_xticklabels(["128kB", "256kB", "512kB", "1MB"])
    ax.set_xlabel("L2 size")
    ax.set_ylabel("L2 MPKI")
    ax.set_title("GEMM N=128: L2 MPKI vs L2 size (L1D=32kB, O3)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "l2_mpki_vs_l2_n128.png", dpi=180)
    plt.close(fig)

    # Working-set sweep with baseline cache settings
    n_rows = [
        row
        for row in rows
        if row.get("l1d_size") == "32kB"
        and row.get("l2_size") == "256kB"
        and "baseline" in row.get("tag", "")
    ]
    n_rows = [row for row in n_rows if parse_n(row.get("binary_args", "")) > 0]
    n_rows.sort(key=lambda r: parse_n(r["binary_args"]))
    n_vals = [parse_n(r["binary_args"]) for r in n_rows]
    n_ipc = [float(r["ipc"]) for r in n_rows]
    n_sim_seconds = [float(r["sim_seconds"]) for r in n_rows]

    fig, ax1 = plt.subplots(figsize=(7.5, 4.8))
    ax1.plot(n_vals, n_ipc, marker="o", linewidth=2, label="IPC")
    ax1.set_xlabel("Matrix size N (N x N)")
    ax1.set_ylabel("IPC")
    ax1.grid(alpha=0.3)
    ax1.set_title("GEMM O3 baseline caches: scaling with problem size")

    ax2 = ax1.twinx()
    ax2.plot(
        n_vals,
        n_sim_seconds,
        marker="s",
        linewidth=2,
        color="#e7298a",
        label="simSeconds",
    )
    ax2.set_ylabel("simSeconds")

    lines = ax1.get_lines() + ax2.get_lines()
    labels = [ln.get_label() for ln in lines]
    ax1.legend(lines, labels, loc="upper left")
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "scaling_ipc_simseconds_vs_n.png", dpi=180)
    plt.close(fig)

    print(f"Wrote plots to {PLOT_DIR}")


if __name__ == "__main__":
    main()
