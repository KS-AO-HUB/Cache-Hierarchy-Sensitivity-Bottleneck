#!/usr/bin/env python3
"""
Build the final figure pack from results_summary_o3.csv.

Writes png files to /workspace/project/experiments/plot_pack/.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


CSV_PATH = Path("/workspace/project/experiments/results_summary_o3.csv")
OUT_DIR = Path("/workspace/project/experiments/plot_pack")


def to_kb(size_text: str) -> int:
    s = size_text.strip().upper()
    if s.endswith("MB"):
        return int(s[:-2]) * 1024
    if s.endswith("KB"):
        return int(s[:-2])
    return int(s)


def load_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def plot_n128_l2(rows: list[dict[str, str]]) -> None:
    data = [
        r
        for r in rows
        if r.get("benchmark") == "gemm"
        and r.get("binary_args") == "128 ijk"
        and r.get("l1d_size") == "32kB"
        and r.get("l2_size") in {"128kB", "256kB", "512kB", "1MB"}
        and r.get("run_status") == "success"
    ]
    data.sort(key=lambda r: to_kb(r["l2_size"]))
    x = [to_kb(r["l2_size"]) for r in data]
    ipc = [float(r["ipc"]) for r in data]
    l2mpki = [float(r["l2_mpki"]) for r in data]

    fig, ax1 = plt.subplots(figsize=(7.8, 4.8))
    ax1.plot(x, ipc, marker="o", linewidth=2, label="IPC")
    ax1.set_xscale("log", base=2)
    ax1.set_xticks(x)
    ax1.set_xticklabels([r["l2_size"] for r in data])
    ax1.set_xlabel("L2 size")
    ax1.set_ylabel("IPC")
    ax1.grid(alpha=0.3)
    ax1.set_title("GEMM N=128: IPC and L2 MPKI vs L2 size")

    ax2 = ax1.twinx()
    ax2.plot(x, l2mpki, marker="s", linewidth=2, color="#d95f02", label="L2 MPKI")
    ax2.set_ylabel("L2 MPKI")

    lines = ax1.get_lines() + ax2.get_lines()
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "01_n128_ipc_l2mpki_vs_l2.png", dpi=180)
    plt.close(fig)


def plot_n128_l1(rows: list[dict[str, str]]) -> None:
    data = [
        r
        for r in rows
        if r.get("benchmark") == "gemm"
        and r.get("binary_args") == "128 ijk"
        and r.get("l2_size") == "256kB"
        and r.get("l1d_size") in {"16kB", "32kB", "64kB"}
        and r.get("run_status") == "success"
    ]
    data.sort(key=lambda r: to_kb(r["l1d_size"]))
    x = [to_kb(r["l1d_size"]) for r in data]
    ipc = [float(r["ipc"]) for r in data]

    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    ax.plot(x, ipc, marker="o", linewidth=2)
    ax.set_xticks(x)
    ax.set_xticklabels([r["l1d_size"] for r in data])
    ax.set_xlabel("L1D size")
    ax.set_ylabel("IPC")
    ax.grid(alpha=0.3)
    ax.set_title("GEMM N=128: IPC vs L1D size (L2 fixed at 256kB)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "02_n128_ipc_vs_l1d.png", dpi=180)
    plt.close(fig)


def plot_scaling(rows: list[dict[str, str]]) -> None:
    data = [
        r
        for r in rows
        if r.get("benchmark") == "gemm"
        and r.get("l1d_size") == "32kB"
        and r.get("l2_size") == "256kB"
        and "baseline" in r.get("tag", "")
        and r.get("run_status") == "success"
    ]
    data.sort(key=lambda r: int(r["binary_args"].split()[0]))
    nvals = [int(r["binary_args"].split()[0]) for r in data]
    ipc = [float(r["ipc"]) for r in data]
    l2mpki = [float(r["l2_mpki"]) for r in data]

    fig, ax1 = plt.subplots(figsize=(7.8, 4.8))
    ax1.plot(nvals, ipc, marker="o", linewidth=2, label="IPC")
    ax1.set_xlabel("Matrix size N")
    ax1.set_ylabel("IPC")
    ax1.grid(alpha=0.3)
    ax1.set_title("GEMM baseline caches: scaling behavior")

    ax2 = ax1.twinx()
    ax2.plot(nvals, l2mpki, marker="s", linewidth=2, color="#7570b3", label="L2 MPKI")
    ax2.set_ylabel("L2 MPKI")

    lines = ax1.get_lines() + ax2.get_lines()
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "03_baseline_scaling_ipc_l2mpki_vs_n.png", dpi=180)
    plt.close(fig)


def plot_remediation(rows: list[dict[str, str]]) -> None:
    wanted = [
        "n256_baseline_l1d32_l2_256",
        "n256_l1d32_l2_512",
        "n256_l1d32_l2_1MB",
        "n256_l1d32_l2_2MB",
    ]
    by_tag = {r["tag"]: r for r in rows if r.get("tag") in wanted and r.get("run_status") == "success"}
    data = [by_tag[t] for t in wanted if t in by_tag]

    base_time = float(by_tag["n256_baseline_l1d32_l2_256"]["sim_seconds"])
    labels = [r["l2_size"] for r in data]
    speedup = [base_time / float(r["sim_seconds"]) for r in data]

    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    bars = ax.bar(labels, speedup)
    ax.set_ylabel("Speedup vs 256kB baseline")
    ax.set_xlabel("L2 size")
    ax.set_title("GEMM N=256: performance gain from larger L2")
    ax.grid(axis="y", alpha=0.3)
    for bar, val in zip(bars, speedup):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.03, f"{val:.2f}x", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "04_n256_l2_remediation_speedup.png", dpi=180)
    plt.close(fig)


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    plot_n128_l2(rows)
    plot_n128_l1(rows)
    plot_scaling(rows)
    plot_remediation(rows)
    print(f"Wrote final graph pack to {OUT_DIR}")


if __name__ == "__main__":
    main()
