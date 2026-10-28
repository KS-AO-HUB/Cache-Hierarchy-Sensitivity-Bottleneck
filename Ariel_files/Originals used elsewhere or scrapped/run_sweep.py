#!/usr/bin/env python3
"""
Runs all gem5 experiments for the cache hierarchy project.
Each experiment = one benchmark × one configuration.
Results go into /workspace/project/results/<benchmark>/<tag>/
"""

import subprocess
import os
import json
import sys

# === PATHS ===
GEM5_BIN = "/opt/gem5/build/X86/gem5.opt"
CONFIG_SCRIPT = "/workspace/project/configs/run_experiment.py"
RESULTS_DIR = "/workspace/project/results"

# === BENCHMARKS ===
# (name, path to binary, arguments)
BENCHMARKS = [
    ("gemm", "/workspace/project/benchmarks/gemm_x86", "32 ijk"),
    ("pointer_chase", "/workspace/project/benchmarks/pointer_chase_x86", "8192 500000"),
    ("bfs", "/workspace/project/benchmarks/bfs_x86", "4096 6"),
]

# === BASELINE CONFIG ===
BASELINE = {
    "l1d_size": "32kB",
    "l1i_size": "32kB",
    "l2_size": "256kB",
    "cpu_type": "O3CPU",
}

# === PARAMETER SWEEPS ===
# Each sweep changes ONE parameter from baseline
SWEEPS = [
    # L2 size sweep
    ("l2_size", ["128kB", "256kB", "512kB", "1MB"]),
    # L1D size sweep
    ("l1d_size", ["16kB", "32kB", "64kB"]),
]

# === CPU COMPARISON ===
CPU_TYPES = ["TimingSimpleCPU", "O3CPU"]


def run_one(bench_name, binary_path, binary_args, config, tag):
    """Run a single gem5 simulation."""
    outdir = os.path.join(RESULTS_DIR, bench_name, tag)
    os.makedirs(outdir, exist_ok=True)

    cmd = [
        GEM5_BIN,
        f"--outdir={outdir}",
        CONFIG_SCRIPT,
        f"--binary={binary_path}",
        f"--binary_args={binary_args}",
        f"--l1d_size={config['l1d_size']}",
        f"--l1i_size={config['l1i_size']}",
        f"--l2_size={config['l2_size']}",
        f"--cpu_type={config['cpu_type']}",
    ]

    print(f"\n{'='*60}")
    print(f"  RUNNING: {bench_name} | {tag}")
    print(
        f"  Config:  L1D={config['l1d_size']} L2={config['l2_size']} CPU={config['cpu_type']}"
    )
    print(f"{'='*60}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Save stdout/stderr for debugging
    with open(os.path.join(outdir, "stdout.txt"), "w") as f:
        f.write(result.stdout)
    with open(os.path.join(outdir, "stderr.txt"), "w") as f:
        f.write(result.stderr)

    # Save config for reproducibility
    with open(os.path.join(outdir, "config_used.json"), "w") as f:
        json.dump(config, f, indent=2)

    if result.returncode != 0:
        print(f"  ❌ FAILED — check {outdir}/stderr.txt")
        # Print last 5 lines of stderr for quick debugging
        lines = result.stderr.strip().split("\n")
        for line in lines[-5:]:
            print(f"     {line}")
        return False
    else:
        print(f"  ✅ Done")
        return True


def main():
    total = 0
    passed = 0
    failed = 0

    # --- 1. BASELINES ---
    print("\n" + "=" * 60)
    print("  PHASE 1: BASELINES")
    print("=" * 60)
    for bench_name, binary_path, binary_args in BENCHMARKS:
        total += 1
        if run_one(bench_name, binary_path, binary_args, BASELINE, "baseline"):
            passed += 1
        else:
            failed += 1

    # --- 2. PARAMETER SWEEPS ---
    for param, values in SWEEPS:
        print("\n" + "=" * 60)
        print(f"  PHASE 2: SWEEP {param}")
        print("=" * 60)
        for val in values:
            config = BASELINE.copy()
            config[param] = val
            tag = f"sweep_{param}_{val}"
            for bench_name, binary_path, binary_args in BENCHMARKS:
                total += 1
                if run_one(bench_name, binary_path, binary_args, config, tag):
                    passed += 1
                else:
                    failed += 1

    # --- 3. CPU COMPARISON ---
    print("\n" + "=" * 60)
    print("  PHASE 3: CPU COMPARISON")
    print("=" * 60)
    for cpu in CPU_TYPES:
        config = BASELINE.copy()
        config["cpu_type"] = cpu
        tag = f"cpu_{cpu}"
        for bench_name, binary_path, binary_args in BENCHMARKS:
            total += 1
            if run_one(bench_name, binary_path, binary_args, config, tag):
                passed += 1
            else:
                failed += 1

    # --- SUMMARY ---
    print("\n" + "=" * 60)
    print(f"  ALL DONE: {passed}/{total} passed, {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    main()
