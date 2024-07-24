"""
Combines field-separated-values files containing VAST runtime data into one
Markdown table.

Each file is expected to have two columns: "Compilation unit" and "Runtime or
failure". The first column is the name of the file VAST was run on. The second
column is either a floating point number representing how long it took
vast-front, in seconds, to run on the file; or the string literal FAIL if
vast-front failed to process the file.
"""

COMPILATION_UNIT_COLUMN_NAME = "Compilation unit"
RUNTIME_OR_FAILURE_COLUMN_NAME = "Runtime or failure"

import argparse
import json
import pandas
import pathlib
import sys
from typing import Optional


class Arguments(argparse.Namespace):
    """Program arguments"""

    column_filename_json: str
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

    parser.add_argument(
        "column_filename_json",
        type=str,
        help="A JSON object mapping column names to the names of the files containing their data.",
    )
    parser.add_argument(
        "--output_filepath",
        "-o",
        type=pathlib.Path,
        help="Output filepath (if omitted, result is printed to stdout).",
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

    totals = ["Total passing"]
    for i in range(1, len(dataframe.columns)):
        passing = sum(dataframe.iloc[:, i] != "FAIL")
        total = len(dataframe)
        ratio = f"{passing}/{total}"
        totals.append(ratio)
    totals_row = pandas.DataFrame([totals], columns=dataframe.columns)
    # See https://stackoverflow.com/a/67678982/6824430
    return pandas.concat([totals_row, dataframe], ignore_index=True)


def main() -> int:
    arguments = parse_args()
    column_names_filenames = list(json.loads(arguments.column_filename_json).items())

    if 0 == len(column_names_filenames):
        print("error: No files to convert to Markdown", file=sys.stderr)
        return 1

    # Initialize the final dataframe with the data in the first table.

    final_dataframe = pandas.read_csv(
        column_names_filenames[0][1], sep=arguments.field_separator
    )
    final_dataframe.rename(
        columns={RUNTIME_OR_FAILURE_COLUMN_NAME: column_names_filenames[0][0]},
        inplace=True,
    )

    # Add the last column of the rest of the tables to the final dataframe.
    for column_name, filename in column_names_filenames[1:]:
        dataframe = pandas.read_csv(filename, sep=arguments.field_separator)
        if not (
            final_dataframe.loc[:, COMPILATION_UNIT_COLUMN_NAME].equals(
                dataframe.loc[:, COMPILATION_UNIT_COLUMN_NAME]
            )
        ):
            print(
                f"error: Compilation units of {filename} do not match that of previous files.",
                file=sys.stderr,
            )
            return 1
        final_dataframe.insert(
            len(final_dataframe.columns),
            column_name,
            dataframe.loc[:, RUNTIME_OR_FAILURE_COLUMN_NAME],
        )

    final_dataframe = add_total_passing(final_dataframe)

    markdown = final_dataframe.to_markdown(index=False)
    if markdown is None:
        print("error: Could not convert input to Markdown", file=sys.stderr)
        return 1
    if arguments.output_filepath is not None:
        with open(arguments.output_filepath, "w") as fp:
            fp.write(markdown)
    else:
        print(markdown)

    return 0


if "__main__" == __name__:
    exit(main())
