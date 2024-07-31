# Guide to running the VAST Linux kernel benchmark

This document lists the steps to download, configure, and build the Linux
kernel; and run `vast-front` on each of its compilation units.

## Foreword

These instructions were tested and written on `Ubuntu 22.04.4 LTS x86_64`.

## Prerequisites

Download the following dependencies using your own package manager:

- [GNU Make](https://www.gnu.org/software/make/)
- [Clang/LLVM/LLD 18.1.8](https://github.com/llvm/llvm-project/releases/tag/llvmorg-18.1.8)
- [Python3](https://www.python.org/downloads/)

Download `VAST` from GitHub and follows its setup instructions:

- [VAST](https://github.com/trailofbits/vast)

## Setting up Linux

1. Download the most recent version of the kernel:

    ```bash
    git clone https://github.com/torvalds/linux.git --depth=1
    ```

1. Configure the kernel with its default configuration:

    ```bash
    cd linux/
    make defconfig
    ```

1. Build the kernel:

    ```bash
    cd linux/
    make LLVM=1
    ```

    Note that we use the `LLVM=1` flag to build the kernel with Clang-compatible
    arguments only and without any GCC-specific arguments.

1. Run the kernel's `gen_compile_commands.py` script to generate a compilation
   database of the the kernel's source files:

    ```sh
    python3 `scripts/clang-tools/gen_compile_commands.py`
    ```

## Running VAST on Linux

Run the python script `run_vast_benchmark.py` with the appropriate arguments,
e.g.,

For `vast-front`:

```bash
python3 run_vast_benchmark.py \
    vast-front \
    compile_commands.json \
    vast_linux_kernel_mlir/ \
    --num_processes=8 \
    --vast_option="-xc" \
    --vast_option="-vast-emit-mlir=hl" \
    > vast_linux_kernel_times.tsv
```

This will create a directory called `vast_linux_kernel_mlir`with all the
resulting MLIR and error log files, and a file called
`vast_linux_kernel_times.tsv` with the benchmark's runtime metrics.

For detailed information on all the benchmarks script's options, run:

```bash
python3 run_vast_benchmark.py --help
```

## Interpreting benchmark timing results

The `run_vast_benchmark.py` script prints its timing metrics to stdout. For each
compilation unit that `vast-front` successfully processes, the script prints the
name of the compilation unit's source file alongside the time necessary for
`vast-front` to lower it to MLIR. If `vast-front` fails to process the
compilation unit, then it prints the string literal `FAIL` instead.
