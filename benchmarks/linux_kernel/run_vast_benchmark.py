import argparse
import dataclasses
import multiprocessing
import pathlib
from datetime import datetime, timedelta
import sys
import json
import subprocess
import os
from typing import Optional


class Arguments(argparse.Namespace):
    """
    This script's arguments.
    """

    vast_path: pathlib.Path
    compile_commands_file: pathlib.Path
    output_directory: Optional[pathlib.Path]
    print_commands: bool
    num_processes: int
    vast_option: list[str]
    print_errors: bool


def parse_arguments() -> Arguments:
    description = """
Run vast-front on all the files in the given compilation database. When
vast-front successfully lowers a compilation unit to MLIR, the result is placed
in the given output directory. When vast-front fails to lower a compilation unit
to MLIR, a log file containing the stderr output is placed in the output
directory instead. The time needed to lower each compilation unit to MLIR is
printed to stdout in TSV format. The benchmark's progress is printed to
stderr.""".lstrip()

    # Positional arguments.

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "vast_path", type=pathlib.Path, help="Path to vast-front executable."
    )
    parser.add_argument(
        "compile_commands_file",
        type=pathlib.Path,
        help="Path to the Clang compilation database for the benchmark.",
    )

    # Optional arguments.
    parser.add_argument(
        "--output_directory",
        type=pathlib.Path,
        help="Directory to place results. If omitted, then results will be discarded.",
    )

    print_commands_help = """Enable this option to print the vast-front
commands that are run on each compilation unit. Turned off by
default.""".replace(
        "\n", " "
    )
    parser.add_argument(
        "--print_commands",
        action=argparse.BooleanOptionalAction,
        help=print_commands_help,
    )
    num_processes_help = """The number of processes to use to run the benchmark. Defaults to
the number of CPUS on this machine.""".replace(
        "\n", " "
    )
    parser.add_argument(
        "--num_processes",
        type=int,
        default=os.cpu_count(),
        help=num_processes_help,
    )
    vast_option_help = """Additional vast-front options. Can be specified
multiple times to specify multiple
options.""".replace(
        "\n", " "
    )
    parser.add_argument("--vast_option", action="append", help=vast_option_help)
    print_errors_help = """Enable this option to print any errors that occur
when running vast-front on each compilation unit. Turned off by
default.""".replace(
        "\n", " "
    )
    parser.add_argument(
        "--print_errors",
        action=argparse.BooleanOptionalAction,
        help=print_errors_help,
    )

    arguments = Arguments()
    parser.parse_args(namespace=arguments)

    return arguments


@dataclasses.dataclass
class CompileCommand:
    """
    Represents a Clang compile command.
    """

    directory: str
    file: str
    output: str
    arguments: Optional[list[str]] = None
    command: Optional[str] = None

    def argument_parts(self) -> list[str]:
        if self.arguments is not None:
            return self.arguments
        elif self.command is not None:
            return self.command.split()
        raise ValueError("No argument or command")


def load_compile_commands(filepath: pathlib.Path) -> list[CompileCommand]:
    """
    Loads the compilation database at the given path and returns it as a
    list.
    """

    with open(filepath) as fp:
        return [CompileCommand(**command) for command in json.load(fp)]


@dataclasses.dataclass
class VASTBenchmarkInput:
    """
    Contains all the necessary information to run vast-front on a Clang
    compilation unit.
    """

    vast_path: pathlib.Path
    vast_option: list[str]
    compile_command: CompileCommand
    output_directory: Optional[pathlib.Path]
    print_commands: bool


def run_vast_on_compile_command(
    vast_benchmark_input: VASTBenchmarkInput,
) -> timedelta | str:
    """
    Reuns vast on the given compilation unit with the given inputs. If
    successful, returns the time elapsed while lowering the compilation unit to
    MLIR; otherwise returns a string containing the failure message.
    """

    # We have to pack the arguments into a dataclass like this since Pool.imap()
    # requires multiprocessed functions to accept a single argument.
    (
        vast_path,
        vast_option,
        compile_command,
        output_directory,
        print_commands,
    ) = dataclasses.astuple(vast_benchmark_input)

    # Turn this back into a dataclass since astuple() works recursively.
    compile_command = CompileCommand(*compile_command)

    input_filepath = pathlib.PurePath(os.path.abspath(compile_command.file))
    input_mlir_name = input_filepath.with_suffix(".mlir").name

    output_filepath = pathlib.Path()
    if output_directory is not None:
        output_filepath = output_directory / input_mlir_name
        while output_filepath.is_file():
            output_name = output_filepath.name
            output_filepath = output_filepath.with_name(output_name + "_")

    original_arguments: list[str] = compile_command.argument_parts()

    # Escape parentheses that may be presesnt in the command.
    escaped_arguments = [
        arg.replace("(", "\\(").replace(")", "\\)") for arg in original_arguments
    ]

    # If the -cc1 flag was passed, move it to the front of the arguments list.
    has_cc1 = "-cc1" in escaped_arguments
    if has_cc1:
        escaped_arguments.remove("-cc1")

    command = f"cd {compile_command.directory} && " + " ".join(
        [str(vast_path)]
        + (["-cc1"] if has_cc1 else [])
        + vast_option
        # Skip compiler name, -o flag, and original output and input filenames.
        + escaped_arguments[1:-3]
        + ["-w", "-Wno-error", "-Wno-everything"]
        + [str(input_filepath)]
        + ["-o", str(output_filepath) if output_directory is not None else "/dev/null"]
    )

    if print_commands:
        print(command, file=sys.stderr)

    begin = datetime.now()
    cp = subprocess.run(command, shell=True, capture_output=True)
    elapsed = datetime.now() - begin
    failed = 0 != cp.returncode

    if failed:
        return cp.stderr.decode()

    return elapsed


def print_tsv_row(row: list[str]):
    print("\t".join(row))


def run_vast_on_compile_commands(
    vast_path: pathlib.Path,
    vast_option: list[str],
    compile_commands: list[CompileCommand],
    linux_directory: pathlib.Path,
    output_directory: Optional[pathlib.Path],
    num_processes: int,
    print_commands: bool,
    print_errors: bool,
) -> int:
    """
    Returns the number of compilation units vast-front successfully lowers to
    MLIR.
    """
    tsv_header = ["Compilation unit", "Runtime or failure"]
    num_passing = 0

    if output_directory is not None:
        output_directory.mkdir(parents=True, exist_ok=True)
    print_tsv_row(tsv_header)
    vast_benchmark_inputs = [
        VASTBenchmarkInput(
            vast_path=vast_path,
            vast_option=vast_option,
            compile_command=compile_command,
            output_directory=output_directory,
            print_commands=print_commands,
        )
        for compile_command in compile_commands
    ]

    with multiprocessing.Pool(num_processes) as pool:
        for (i, elapsed_or_error), compile_command in zip(
            enumerate(pool.imap(run_vast_on_compile_command, vast_benchmark_inputs), 1),
            compile_commands,
        ):
            filepath = "." + compile_command.file.removeprefix(str(linux_directory))
            failed = isinstance(elapsed_or_error, str)
            num_passing += int(not failed)
            row = [filepath]
            fraction = f"{i}/{len(compile_commands)}"

            if not failed:
                seconds = elapsed_or_error.seconds
                microseconds = str(elapsed_or_error.microseconds)[:2]
                formatted_timedelta = f"{seconds}.{microseconds}"
                row.append(formatted_timedelta)
                print(f"finished processing {fraction} files", file=sys.stderr)
            else:
                row.append("FAIL")
                print(f"error processing {fraction} files", file=sys.stderr)
                if print_errors:
                    print(elapsed_or_error, file=sys.stderr)
                if output_directory is not None:
                    input_filepath = pathlib.PurePath(os.path.abspath(filepath))
                    input_log_name = input_filepath.with_suffix(".log").name
                    log_filepath = output_directory / input_log_name
                    while log_filepath.is_file():
                        log_name = log_filepath.name
                        log_filepath = log_filepath.with_name(log_name + "_")
                    with open(log_filepath, "w") as fp:
                        print(elapsed_or_error, file=fp)

            print_tsv_row(row)

    return num_passing


def main() -> int:
    arguments = parse_arguments()

    compile_commands_file = arguments.compile_commands_file.absolute()
    compile_commands = load_compile_commands(compile_commands_file)

    # Get the path to the Linux directory so we can remove it from the output.
    linux_directory = compile_commands_file.parent

    output_directory = arguments.output_directory
    if output_directory is not None:
        output_directory = output_directory.absolute()

    num_passing = run_vast_on_compile_commands(
        vast_path=pathlib.Path(arguments.vast_path),
        vast_option=arguments.vast_option,
        compile_commands=compile_commands,
        linux_directory=linux_directory,
        output_directory=output_directory,
        num_processes=arguments.num_processes,
        print_commands=arguments.print_commands,
        print_errors=arguments.print_errors,
    )

    print(f"Total successful: {num_passing}/{len(compile_commands)}", file=sys.stderr)

    return 0


if "__main__" == __name__:
    exit(main())
