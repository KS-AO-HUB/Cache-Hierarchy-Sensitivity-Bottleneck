# Cache Hierarchy Sensitivity & Bottleneck Attribution for GEMM (gem5 O3CPU)

A cycle-accurate microarchitectural study using the **gem5 O3CPU** model to identify the
dominant cache bottleneck for a dense GEMM kernel, attribute stalls via CPI decomposition,
and validate a targeted L2 remediation that delivers a **3.72× speedup** at the cost–benefit
knee point.

**Course:** EEL 6764 — Principles of Computer Architecture (Spring 2026), University of South Florida
**Team:** *Cache Me If You Can* — Ariel Gomez Garcia, Jason Olefson, Ryan Carbone, Sebastien Ghent

---

## TL;DR

- Built a parameterized gem5 O3CPU sweep harness driven by JSON manifests (13 final configurations: a 10-run main sweep plus 3 additional L2 sizes at $N=256$).
- Isolated **L2 capacity** as the first-order bottleneck for ijk-order GEMM via a 3-step methodology: L1D sweep → L2 sweep → working-set scaling.
- At $N=256$ baseline, attributed **~79% of cycles to memory-system stalls** via CPI decomposition (L2 MPKI = 137.68).
- Validated remediation: enlarging L2 from 256 kB → 1 MB yields **3.72× speedup** (CPI $2.21 \to 0.59$, L2 MPKI $137.68 \to 0.094$).
- Established **~0.2% diminishing returns beyond 1 MB**, giving a defensible cost–benefit knee at $4\times$ baseline L2 capacity.

📄 Full write-up: [`Project Report.pdf`](./Project%20Report.pdf)

---

## Headline Result

**L2 remediation at $N=256$ (L1D fixed at 32 kB):**

| L2 size | IPC | CPI | L2 MPKI | simSeconds | Speedup | Capacity |
|---:|---:|---:|---:|---:|---:|---:|
| 256 kB (baseline) | 0.452 | 2.214 | 137.68 | 0.18078 | 1.00× | 1× |
| 512 kB | 0.525 | 1.906 | 24.41 | 0.15567 | 1.16× | 2× |
| **1 MB** | **1.681** | **0.595** | **0.094** | **0.04859** | **3.72×** | **4×** |
| 2 MB | 1.684 | 0.594 | 0.015 | 0.04851 | 3.73× | 8× |

The 512 kB → 1 MB transition is the critical knee: $4\times$ baseline capacity removes the bottleneck; $8\times$ adds only $\approx 0.2\%$ more.

**Why the knee falls there.** In ijk order, every iteration of the outer loop sweeps all of matrix $B$, so the data reused across iterations is essentially $B$ alone ($N^2 \times 8$ bytes), not the full $3N^2 \times 8$-byte footprint. At $N=256$, $B$ is 512 kB: it cannot stay resident in a 512 kB L2 alongside the rows of $A$ and $C$, but fits comfortably in 1 MB. The same rule matches the other sweeps: at $N=128$ ($B$ = 128 kB), L2 misses explode only when L2 shrinks to 128 kB; at $N=192$ ($B$ = 288 kB), the 256 kB baseline L2 is already too small (L2 MPKI 17.3).

---

## Methodology

The bottleneck attribution follows a deliberate three-step elimination:

1. **L1D sweep at fixed L2** — $N=128$, L2 = 256 kB, L1D $\in \{16, 32, 64\}$ kB. IPC varies by $<0.01\%$, ruling L1D out as the limiter.
2. **L2 sweep at fixed L1D** — $N=128$, L1D = 32 kB, L2 $\in \{128\text{ kB}, 256\text{ kB}, 512\text{ kB}, 1\text{ MB}\}$. Halving L2 to 128 kB collapses IPC by $>2.2\times$ and raises L2 MPKI by $>130\times$, identifying L2 as the dominant capacity knob.
3. **Working-set scaling** — $N \in \{32, 64, 128, 192, 256\}$ at baseline caches. Confirms the bottleneck sharpens as the $3N^2 \times 8$-byte footprint exceeds L2 capacity.
4. **CPI decomposition** — using $N=64$ (compute-bound, CPI = 0.47) as the compute baseline, $N=256$ (CPI = 2.21) attributes $1.74$ CPI ($\approx 79\%$ of cycles) to memory-system stalls.
5. **Remediation validation** — L2 sweep at $N=256$ over $\{256\text{ kB}, 512\text{ kB}, 1\text{ MB}, 2\text{ MB}\}$ locates the cost–benefit knee.

All experiments use the gem5 O3CPU (detailed out-of-order) model with the default DRAM model. No gem5 source modifications — all variation is driven through JSON manifests consumed by a Python orchestration layer that enforces O3CPU and writes per-run metadata (`command.sh`, `config_used.json`, `run.log`, `run_record.json`).

---

## Workload

The benchmark used in the final O3 sweep is `gemm_x86` (compiled from `mm_bench.c`): a textbook dense GEMM kernel on double-precision matrices, run in **ijk** loop order, statically compiled for x86 SE-mode execution under gem5. The innermost loop streams along a column of $B$ while accumulating into a single element of $C$ — a deliberately cache-unfriendly access pattern.

The source also implements a **kij** kernel (better row-major locality) for future comparison; only **ijk** was used in this study.

Working-set footprint: $3N^2 \times 8$ bytes, ranging from 24 kB ($N=32$, fits in L1D) to 1.5 MB ($N=256$, exceeds the 256 kB baseline L2).

### Companion microbenchmarks (not part of the final sweep)

Two additional microbenchmarks are included in the repository but were **not run in the final O3CPU sweep matrix**. They were authored and compiled to support possible follow-up studies on irregular and latency-bound access patterns:

| File | Pattern | Purpose |
|---|---|---|
| `bfs.c` | Irregular (BFS over deterministic LCG-generated CSR graph) | Stress associativity and prefetcher under indirection |
| `pointer_chase.c` | Latency-bound (Fisher-Yates shuffled linked list) | Isolate memory latency from bandwidth |

These remain in the repo so the harness can be extended (see *Future Work* in the report).

---

## Key Figures

In `project/experiments/plot_pack/`:

| Figure | Claim Supported |
|---|---|
| `01_n128_ipc_l2mpki_vs_l2.png` | L2-capacity bottleneck at L2 = 128 kB vs. adequately sized L2 ($N=128$) |
| `02_n128_ipc_vs_l1d.png` | L1D size is not the dominant limiter across $\{16, 32, 64\}$ kB |
| `03_baseline_scaling_ipc_l2mpki_vs_n.png` | Transition from compute-efficient to memory-bound as $N$ grows |
| `04_n256_l2_remediation_speedup.png` | 3.72× speedup at 1 MB, diminishing returns at 2 MB |

---

## Repository Layout

```
Cache-Hierarchy-Sensitivity-Bottleneck/
├── Project Report.pdf              # Full written report with figures and analysis
├── Ariel_files/                    # Source benchmarks and early analysis scripts
│   ├── mm_bench.c                  # Dense GEMM (ijk + kij); ijk used in final sweep
│   ├── *_x86                       # Statically compiled SE-mode binaries
│   ├── parse_stats.py              # gem5 stats.txt parser
│   ├── plot_results.py             # Plotting utilities
│   ├── run_experiment.py           # Early single-run driver
│   └── Originals used elsewhere or scrapped/
│       ├── bfs.c                   # Companion microbenchmark (not in final sweep)
│       ├── pointer_chase.c         # Companion microbenchmark (not in final sweep)
│       └── run_sweep.py
├── demo/                           # Early course demo (TimingSimpleCPU, GAPBS BFS) and a trace-based CPI script; not part of the final study
└── project/
    ├── benchmarks/                 # Final compiled benchmarks
    ├── configs/                    # gem5 stdlib configuration
    ├── experiments/
    │   ├── final_o3_manifest.json          # Main 10-run sweep manifest
    │   ├── l2_fix_n256_manifest.json       # N=256 L2 remediation manifest
    │   ├── l2_fix_n256_2mb_resume.json     # Resume manifest for interrupted 2 MB run
    │   ├── results_summary_o3.csv          # Aggregated O3CPU results (source of truth; rows tagged o3_* or cpu_* are early test runs)
    │   ├── logs/                           # Per-session manifest snapshots & summaries
    │   ├── plots/                          # Individual sweep plots
    │   └── plot_pack/                      # Final report figure pack
    ├── results/gemm/               # Per-config gem5 output (stats.txt, config.json, run.log, run_record.json);
    │                               #   cpu_* and o3_l1d* folders are early test runs, not in the final analysis
    └── scripts/
        ├── run_o3_experiments.py           # O3-enforced manifest driver
        ├── summarize_o3_results.py         # Aggregates stats.txt → CSV
        ├── plot_o3_10run.py
        ├── plot_n256_l2_remediation.py
        └── plot_final_report_pack.py
```

---

## Reproducing the Study

**Prerequisites:** gem5 built with x86 support, Python 3.9+, `numpy`, `pandas`, `matplotlib`.

**Paths.** The scripts and manifests use the paths of our setup: the repository at `/workspace` and gem5 at `/opt/gem5/build/X86/gem5.opt`. Either use the same layout, or pass `--gem5_bin`, `--config_script` and `--results_root` to the run script and edit the `binary` paths in the manifests (the plotting scripts read and write under `/workspace/project/experiments/`).

```bash
# 1. Compile the benchmark (x86, static, SE-mode)
gcc -O2 -static -o project/benchmarks/gemm_x86 Ariel_files/mm_bench.c -lm

# 2. Run the main 10-config O3CPU sweep
python3 project/scripts/run_o3_experiments.py \
    --manifest project/experiments/final_o3_manifest.json

# 3. Run the N=256 L2 remediation sweep
python3 project/scripts/run_o3_experiments.py \
    --manifest project/experiments/l2_fix_n256_manifest.json

# 4. Aggregate all stats.txt files into a single CSV
python3 project/scripts/summarize_o3_results.py \
    --results_root project/results \
    --output_csv project/experiments/results_summary_o3.csv

# 5. Regenerate the report figure pack
python3 project/scripts/plot_final_report_pack.py
```

Per-run artifacts (`stats.txt`, `stats.json`, `config.json`, `run.log`, `run_record.json`, `command.sh`) land in `project/results/gemm/<tag>/`. Representative wall-clock runtimes on our host: ≈184–230 s per $N=128$ config, ≈406 s for $N=192$, ≈1307 s for $N=256$ at baseline caches.

---

## Limitations

- **Single workload class in the final sweep** — conclusions are scoped to dense ijk-order GEMM. Sparse / irregular patterns may exhibit different bottleneck profiles (the companion `bfs.c` and `pointer_chase.c` benchmarks remain available for follow-up).
- **Capacity-only cache exploration** — associativity and replacement policy were held constant.
- **Qualitative power/area discussion** — no McPAT or CACTI integration; energy/area trade-offs are reasoned, not modeled.
- **Knee points are configuration-scoped** — the 1 MB L2 knee is specific to $N=256$ on this O3CPU configuration.

See §6 of the report for the full future-work plan (loop-reordered GEMM variants, McPAT/CACTI integration, associativity/replacement sweeps at the knee, extension to a second workload class).

---

## Author

**Ariel Gomez Garcia** — M.S. Computer Science, University of South Florida
[GitHub](https://github.com/KS-AO-HUB) · [Hugging Face](https://huggingface.co/KS-AO-HUB)

*This is a 4-person team project. Numerical results, figures, and the gem5 sweep infrastructure were produced collaboratively by the team listed above.*


