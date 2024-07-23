"""
Combines field-separated-values files containing VAST runtime data into one
Markdown table.

Each file is expected to have two columns: "Compilation unit" and "Runtime or
failure". The first column is the name of the file VAST was run on. The second
column is either a floating point number representing how long it took
vast-front, in seconds, to run on the file; or the string literal FAIL if
vast-front failed to process the file.
"""

import pathlib
import pandas
import argparse
from typing import Optional


class Arguments(argparse.Namespace):
    """
    Program arguments"""

    input_filepath: pathlib.Path
    output_filepath: Optional[pathlib.Path]
    field_separator: str


def parse_args() -> Arguments:
    parser = argparse.ArgumentParser(
        description="""
Combines field-separated-values files containing VAST runtime data into one
Markdown table.

Each file is expected to have two columns: "Compilation unit" and "Runtime or
failure". The first column is the name of the file VAST was run on. The second
column is either a floating point number representing how long it took
vast-front, in seconds, to run on the file; or the string literal FAIL if
vast-front failed to process the file.

The names of the files in the first column must match in all input files""".lstrip()
    )

    parser.add_argument("input_filepath", type=pathlib.Path, help="Input filepath.")
    parser.add_argument(
        "--output_filepath",
        "-o",
        type=pathlib.Path,
        help="Output filepath (if omitted, result is printed to stderr).",
    )
    parser.add_argument(
        "-t",
        "--field-separator",
        type=str,
        default="\t",
        help="Specify a value to use for the field separator (tab by default).",
    )

    arguments = Arguments()
    parser.parse_args(namespace=arguments)
    return arguments


def add_total_passing(dataframe: pandas.DataFrame) -> pandas.DataFrame:
    """
    Counts the number of rows with passing results and adds a row listing this
    number to the given dataframe.
    """
    ...
    passing = sum(dataframe["Runtime or failure"] != "FAIL")
    total = dataframe.index.size
    ratio = f"{passing}/{total}"
    totals_row = pandas.DataFrame([["Total passing", ratio]], columns=dataframe.columns)
    # See https://stackoverflow.com/a/67678982/6824430
    return pandas.concat([totals_row, dataframe], ignore_index=True)


def main() -> int:
    arguments = parse_args()
    dataframe = pandas.read_csv(arguments.input_filepath, sep=arguments.field_separator)

    # NOTE(Brent): For now leave this call commented-out since it makes
    # assumptions about the input's column headers.
    # dataframe = add_total_passing(dataframe)

    markdown = dataframe.to_markdown(index=False)
    if markdown is None:
        raise ValueError("error: could not convert input to markdown")
    if arguments.output_filepath is not None:
        with open(arguments.output_filepath, "w") as fp:
            fp.write(markdown)
    else:
        print(markdown)

    return 0


if "__main__" == __name__:
    exit(main())
