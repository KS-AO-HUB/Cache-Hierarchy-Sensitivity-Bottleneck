"""
plot_results.py — Generate publication-quality plots from gem5 sweep results.

Reads /workspace/project/results_summary.csv (produced by parse_stats.py)
and generates:
  1. IPC vs L2 Size (per benchmark)
  2. IPC vs L1D Size (per benchmark)
  3. CPU Comparison bar chart (TimingSimpleCPU vs O3CPU)
  4. L1D MPKI vs L2 Size
  5. L2 MPKI vs L2 Size
  6. CPI Stacked/Grouped comparison
  7. Miss Rate summary

Usage:
    python3 /workspace/project/scripts/plot_results.py

Output directory: /workspace/project/plots/
"""

import os
import sys
import re
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # headless backend
import matplotlib.pyplot as plt
import numpy as np

# ── Configuration ──────────────────────────────────────────────────────────
CSV_PATH = "/workspace/project/results_summary.csv"
PLOT_DIR = "/workspace/project/plots"
os.makedirs(PLOT_DIR, exist_ok=True)

# Benchmark display names and colors
BENCH_COLORS = {
    "gemm": "#2196F3",
    "bfs": "#FF9800",
    "pointer_chase": "#4CAF50",
}
BENCH_LABELS = {
    "gemm": "GEMM (compute-bound)",
    "bfs": "BFS (irregular)",
    "pointer_chase": "Pointer Chase (latency-bound)",
}

# ── Helpers ────────────────────────────────────────────────────────────────


def size_to_kb(s):
    """Convert '128kB', '1MB' etc. to integer kB for sorting."""
    s = s.strip().upper()
    if s.endswith("MB"):
        return int(s.replace("MB", "")) * 1024
    elif s.endswith("KB"):
        return int(s.replace("KB", ""))
    return int(s)


def size_label(kb):
    """Pretty-print kB value."""
    if kb >= 1024:
        return f"{kb // 1024} MB"
    return f"{kb} kB"


def extract_sweep_param(tag, prefix):
    """Extract parameter value from tag like 'sweep_l2_size_512kB'."""
    if tag.startswith(prefix):
        return tag[len(prefix) :]
    return None


def load_data():
    if not os.path.exists(CSV_PATH):
        print(f"❌ CSV not found at {CSV_PATH}")
        print("   Run parse_stats.py first.")
        sys.exit(1)
    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {len(df)} rows from {CSV_PATH}")
    print(f"Benchmarks: {df['benchmark'].unique()}")
    print(f"Tags: {df['tag'].unique()}")
    return df


# ── Plot 1: IPC vs L2 Size ────────────────────────────────────────────────


def plot_ipc_vs_l2(df):
    fig, ax = plt.subplots(figsize=(8, 5))

    for bench in ["gemm", "bfs", "pointer_chase"]:
        rows = []
        for _, row in df[df["benchmark"] == bench].iterrows():
            tag = row["tag"]
            val = extract_sweep_param(tag, "sweep_l2_size_")
            if val is None and tag == "baseline":
                val = "256kB"  # baseline uses 256kB L2
                # Only include baseline if there's no explicit 256kB sweep point
                explicit = df[
                    (df["benchmark"] == bench) & (df["tag"] == "sweep_l2_size_256kB")
                ]
                if len(explicit) > 0:
                    continue
            if val is not None:
                rows.append({"size_kb": size_to_kb(val), "IPC": row["IPC"]})

        if not rows:
            continue
        sub = pd.DataFrame(rows).sort_values("size_kb")
        ax.plot(
            sub["size_kb"],
            sub["IPC"],
            marker="o",
            linewidth=2,
            markersize=7,
            color=BENCH_COLORS[bench],
            label=BENCH_LABELS[bench],
        )

    ax.set_xscale("log", base=2)
    ax.set_xticks([128, 256, 512, 1024])
    ax.set_xticklabels(["128 kB", "256 kB", "512 kB", "1 MB"])
    ax.set_xlabel("L2 Cache Size", fontsize=12)
    ax.set_ylabel("IPC", fontsize=12)
    ax.set_title("IPC vs L2 Cache Size (L1D = 32 kB, O3CPU)", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = os.path.join(PLOT_DIR, "ipc_vs_l2_size.png")
    fig.savefig(path, dpi=150)
    print(f"  ✅ {path}")
    plt.close(fig)


# ── Plot 2: IPC vs L1D Size ───────────────────────────────────────────────


def plot_ipc_vs_l1d(df):
    fig, ax = plt.subplots(figsize=(8, 5))

    for bench in ["gemm", "bfs", "pointer_chase"]:
        rows = []
        for _, row in df[df["benchmark"] == bench].iterrows():
            tag = row["tag"]
            val = extract_sweep_param(tag, "sweep_l1d_size_")
            if val is None and tag == "baseline":
                val = "32kB"
                explicit = df[
                    (df["benchmark"] == bench) & (df["tag"] == "sweep_l1d_size_32kB")
                ]
                if len(explicit) > 0:
                    continue
            if val is not None:
                rows.append({"size_kb": size_to_kb(val), "IPC": row["IPC"]})

        if not rows:
            continue
        sub = pd.DataFrame(rows).sort_values("size_kb")
        ax.plot(
            sub["size_kb"],
            sub["IPC"],
            marker="s",
            linewidth=2,
            markersize=7,
            color=BENCH_COLORS[bench],
            label=BENCH_LABELS[bench],
        )

    ax.set_xscale("log", base=2)
    ax.set_xticks([16, 32, 64])
    ax.set_xticklabels(["16 kB", "32 kB", "64 kB"])
    ax.set_xlabel("L1D Cache Size", fontsize=12)
    ax.set_ylabel("IPC", fontsize=12)
    ax.set_title("IPC vs L1D Cache Size (L2 = 256 kB, O3CPU)", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = os.path.join(PLOT_DIR, "ipc_vs_l1d_size.png")
    fig.savefig(path, dpi=150)
    print(f"  ✅ {path}")
    plt.close(fig)


# ── Plot 3: CPU Comparison (Grouped Bar) ──────────────────────────────────


def plot_cpu_comparison(df):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    benchmarks = ["gemm", "bfs", "pointer_chase"]
    cpu_types = ["TimingSimpleCPU", "O3CPU"]
    cpu_colors = {"TimingSimpleCPU": "#9E9E9E", "O3CPU": "#E91E63"}

    x = np.arange(len(benchmarks))
    width = 0.35

    # IPC comparison
    ax = axes[0]
    for i, cpu in enumerate(cpu_types):
        ipcs = []
        for bench in benchmarks:
            row = df[(df["benchmark"] == bench) & (df["tag"] == f"cpu_{cpu}")]
            if len(row) == 0:
                # Fall back to baseline for O3CPU
                if cpu == "O3CPU":
                    row = df[(df["benchmark"] == bench) & (df["tag"] == "baseline")]
            ipcs.append(row["IPC"].values[0] if len(row) > 0 else 0)
        ax.bar(
            x + i * width - width / 2,
            ipcs,
            width,
            label=cpu,
            color=cpu_colors[cpu],
            edgecolor="white",
        )

    ax.set_ylabel("IPC", fontsize=12)
    ax.set_title("IPC: TimingSimpleCPU vs O3CPU", fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels([BENCH_LABELS[b].split(" (")[0] for b in benchmarks])
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # CPI comparison
    ax = axes[1]
    for i, cpu in enumerate(cpu_types):
        cpis = []
        for bench in benchmarks:
            row = df[(df["benchmark"] == bench) & (df["tag"] == f"cpu_{cpu}")]
            if len(row) == 0 and cpu == "O3CPU":
                row = df[(df["benchmark"] == bench) & (df["tag"] == "baseline")]
            cpis.append(row["CPI"].values[0] if len(row) > 0 else 0)
        ax.bar(
            x + i * width - width / 2,
            cpis,
            width,
            label=cpu,
            color=cpu_colors[cpu],
            edgecolor="white",
        )

    ax.set_ylabel("CPI", fontsize=12)
    ax.set_title("CPI: TimingSimpleCPU vs O3CPU", fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels([BENCH_LABELS[b].split(" (")[0] for b in benchmarks])
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    path = os.path.join(PLOT_DIR, "cpu_comparison.png")
    fig.savefig(path, dpi=150)
    print(f"  ✅ {path}")
    plt.close(fig)


# ── Plot 4: MPKI vs L2 Size ──────────────────────────────────────────────


def plot_mpki_vs_l2(df):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    for ax, metric, title in [
        (axes[0], "L1D_MPKI", "L1D MPKI vs L2 Size"),
        (axes[1], "L2_MPKI", "L2 MPKI vs L2 Size"),
    ]:
        for bench in ["gemm", "bfs", "pointer_chase"]:
            rows = []
            for _, row in df[df["benchmark"] == bench].iterrows():
                tag = row["tag"]
                val = extract_sweep_param(tag, "sweep_l2_size_")
                if val is None and tag == "baseline":
                    val = "256kB"
                    explicit = df[
                        (df["benchmark"] == bench)
                        & (df["tag"] == "sweep_l2_size_256kB")
                    ]
                    if len(explicit) > 0:
                        continue
                if val is not None and pd.notna(row.get(metric)):
                    rows.append({"size_kb": size_to_kb(val), metric: row[metric]})

            if not rows:
                continue
            sub = pd.DataFrame(rows).sort_values("size_kb")
            ax.plot(
                sub["size_kb"],
                sub[metric],
                marker="o",
                linewidth=2,
                markersize=7,
                color=BENCH_COLORS[bench],
                label=BENCH_LABELS[bench],
            )

        ax.set_xscale("log", base=2)
        ax.set_xticks([128, 256, 512, 1024])
        ax.set_xticklabels(["128 kB", "256 kB", "512 kB", "1 MB"])
        ax.set_xlabel("L2 Cache Size", fontsize=12)
        ax.set_ylabel(metric.replace("_", " "), fontsize=12)
        ax.set_title(title, fontsize=13)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    fig.tight_layout()
    path = os.path.join(PLOT_DIR, "mpki_vs_l2_size.png")
    fig.savefig(path, dpi=150)
    print(f"  ✅ {path}")
    plt.close(fig)


# ── Plot 5: MPKI vs L1D Size ─────────────────────────────────────────────


def plot_mpki_vs_l1d(df):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    for ax, metric, title in [
        (axes[0], "L1D_MPKI", "L1D MPKI vs L1D Size"),
        (axes[1], "L2_MPKI", "L2 MPKI vs L1D Size"),
    ]:
        for bench in ["gemm", "bfs", "pointer_chase"]:
            rows = []
            for _, row in df[df["benchmark"] == bench].iterrows():
                tag = row["tag"]
                val = extract_sweep_param(tag, "sweep_l1d_size_")
                if val is None and tag == "baseline":
                    val = "32kB"
                    explicit = df[
                        (df["benchmark"] == bench)
                        & (df["tag"] == "sweep_l1d_size_32kB")
                    ]
                    if len(explicit) > 0:
                        continue
                if val is not None and pd.notna(row.get(metric)):
                    rows.append({"size_kb": size_to_kb(val), metric: row[metric]})

            if not rows:
                continue
            sub = pd.DataFrame(rows).sort_values("size_kb")
            ax.plot(
                sub["size_kb"],
                sub[metric],
                marker="s",
                linewidth=2,
                markersize=7,
                color=BENCH_COLORS[bench],
                label=BENCH_LABELS[bench],
            )

        ax.set_xscale("log", base=2)
        ax.set_xticks([16, 32, 64])
        ax.set_xticklabels(["16 kB", "32 kB", "64 kB"])
        ax.set_xlabel("L1D Cache Size", fontsize=12)
        ax.set_ylabel(metric.replace("_", " "), fontsize=12)
        ax.set_title(title, fontsize=13)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    fig.tight_layout()
    path = os.path.join(PLOT_DIR, "mpki_vs_l1d_size.png")
    fig.savefig(path, dpi=150)
    print(f"  ✅ {path}")
    plt.close(fig)


# ── Plot 6: Baseline Summary Table as Figure ─────────────────────────────


def plot_baseline_summary(df):
    """Create a summary bar chart of baseline metrics across all 3 benchmarks."""
    baselines = df[df["tag"] == "baseline"].copy()
    if len(baselines) == 0:
        print("  ⚠️  No baseline rows found, skipping summary plot")
        return

    benchmarks = ["gemm", "bfs", "pointer_chase"]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))
    metrics = ["IPC", "CPI", "L1D_MPKI", "L2_MPKI"]
    titles = ["IPC", "CPI", "L1D MPKI", "L2 MPKI"]

    for ax, metric, title in zip(axes, metrics, titles):
        vals = []
        colors = []
        labels = []
        for bench in benchmarks:
            row = baselines[baselines["benchmark"] == bench]
            if len(row) > 0 and pd.notna(row[metric].values[0]):
                vals.append(row[metric].values[0])
                colors.append(BENCH_COLORS[bench])
                labels.append(BENCH_LABELS[bench].split(" (")[0])
            else:
                vals.append(0)
                colors.append(BENCH_COLORS[bench])
                labels.append(bench)

        ax.bar(labels, vals, color=colors, edgecolor="white", width=0.6)
        ax.set_title(title, fontsize=12)
        ax.grid(True, alpha=0.3, axis="y")
        # Add value labels on bars
        for i, v in enumerate(vals):
            ax.text(i, v + max(vals) * 0.02, f"{v:.2f}", ha="center", fontsize=9)

    fig.suptitle(
        "Baseline Configuration: O3CPU, L1D=32kB, L2=256kB", fontsize=14, y=1.02
    )
    fig.tight_layout()
    path = os.path.join(PLOT_DIR, "baseline_summary.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  ✅ {path}")
    plt.close(fig)


# ── Plot 7: Speedup vs Baseline ──────────────────────────────────────────


def plot_speedup_vs_l2(df):
    """Speedup (T_baseline / T_config) vs L2 size."""
    fig, ax = plt.subplots(figsize=(8, 5))

    for bench in ["gemm", "bfs", "pointer_chase"]:
        baseline = df[(df["benchmark"] == bench) & (df["tag"] == "baseline")]
        if len(baseline) == 0:
            continue
        t_base = baseline["simSeconds"].values[0]

        rows = []
        for _, row in df[df["benchmark"] == bench].iterrows():
            tag = row["tag"]
            val = extract_sweep_param(tag, "sweep_l2_size_")
            if val is None and tag == "baseline":
                val = "256kB"
                explicit = df[
                    (df["benchmark"] == bench) & (df["tag"] == "sweep_l2_size_256kB")
                ]
                if len(explicit) > 0:
                    continue
            if val is not None:
                speedup = t_base / row["simSeconds"] if row["simSeconds"] > 0 else 0
                rows.append({"size_kb": size_to_kb(val), "speedup": speedup})

        if not rows:
            continue
        sub = pd.DataFrame(rows).sort_values("size_kb")
        ax.plot(
            sub["size_kb"],
            sub["speedup"],
            marker="o",
            linewidth=2,
            markersize=7,
            color=BENCH_COLORS[bench],
            label=BENCH_LABELS[bench],
        )

    ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.5, label="Baseline (1.0×)")
    ax.set_xscale("log", base=2)
    ax.set_xticks([128, 256, 512, 1024])
    ax.set_xticklabels(["128 kB", "256 kB", "512 kB", "1 MB"])
    ax.set_xlabel("L2 Cache Size", fontsize=12)
    ax.set_ylabel("Speedup vs Baseline", fontsize=12)
    ax.set_title("Speedup vs L2 Cache Size (relative to 256kB baseline)", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
