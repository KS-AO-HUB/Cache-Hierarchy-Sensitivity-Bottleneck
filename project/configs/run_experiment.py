"""
gem5 config we used for cache experiments.

This script:
  - sets up an x86 SE SimpleBoard
  - lets us tweak L1D/L1I/L2 sizes with flags
  - switches between TimingSimpleCPU and O3CPU
  - runs a static x86 binary

Example:
    /opt/gem5/build/X86/gem5.opt --outdir=<results_dir> \\
        /workspace/project/configs/run_experiment.py \\
        --binary /workspace/project/benchmarks/gemm_x86 \\
        --binary_args "32 ijk" \\
        --l1d_size 32kB \\
        --l2_size 256kB \\
        --cpu_type O3CPU
"""

import argparse
import os

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.cachehierarchies.classic.private_l1_private_l2_cache_hierarchy import (
    PrivateL1PrivateL2CacheHierarchy,
)
from gem5.components.memory.single_channel import SingleChannelDDR4_2400
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator

import m5


def parse_args():
    parser = argparse.ArgumentParser(
        description="Parameterized cache hierarchy experiment"
    )

    # Workload path + args
    parser.add_argument(
        "--binary", type=str, required=True, help="Path to the x86 static binary"
    )
    parser.add_argument(
        "--binary_args",
        type=str,
        default="",
        help="Arguments to pass to the binary (space-separated string)",
    )

    # Cache knobs
    parser.add_argument(
        "--l1d_size",
        type=str,
        default="32kB",
        help="L1 data cache size (e.g., 16kB, 32kB, 64kB)",
    )
    parser.add_argument(
        "--l1i_size", type=str, default="32kB", help="L1 instruction cache size"
    )
    parser.add_argument(
        "--l2_size",
        type=str,
        default="256kB",
        help="L2 cache size (e.g., 128kB, 256kB, 512kB, 1MB)",
    )

    # CPU model
    parser.add_argument(
        "--cpu_type",
        type=str,
        default="O3CPU",
        choices=["TimingSimpleCPU", "O3CPU"],
        help="CPU model: TimingSimpleCPU (in-order) or O3CPU (out-of-order)",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Map CLI CPU string to gem5 enum
    if args.cpu_type == "O3CPU":
        cpu_type = CPUTypes.O3
    else:
        cpu_type = CPUTypes.TIMING

    # Build board pieces
    cache_hierarchy = PrivateL1PrivateL2CacheHierarchy(
        l1d_size=args.l1d_size,
        l1i_size=args.l1i_size,
        l2_size=args.l2_size,
    )

    memory = SingleChannelDDR4_2400()

    processor = SimpleProcessor(
        cpu_type=cpu_type,
        isa=ISA.X86,
        num_cores=1,
    )

    board = SimpleBoard(
        clk_freq="3GHz",
        processor=processor,
        memory=memory,
        cache_hierarchy=cache_hierarchy,
    )

    # Parse optional binary args
    if args.binary_args.strip():
        arg_list = args.binary_args.strip().split()
    else:
        arg_list = []

    board.set_se_binary_workload(
        binary=BinaryResource(local_path=os.path.abspath(args.binary)),
        arguments=arg_list,
    )

    # Create simulator and run
    simulator = Simulator(board=board)

    # Save stats in both text and json
    outdir = m5.options.outdir
    simulator.add_text_stats_output(os.path.join(outdir, "stats.txt"))
    simulator.add_json_stats_output(os.path.join(outdir, "stats.json"))

    print("=" * 60)
    print(f"  Binary:    {args.binary}")
    print(f"  Args:      {arg_list}")
    print(f"  CPU:       {args.cpu_type}")
    print(f"  L1D:       {args.l1d_size}")
    print(f"  L1I:       {args.l1i_size}")
    print(f"  L2:        {args.l2_size}")
    print("=" * 60)

    simulator.run()


if __name__ == "__m5_main__":
    main()
