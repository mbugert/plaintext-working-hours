#!/usr/bin/env python3

import argparse
import datetime
import pathlib
import string

import pandas as pd
from colorama import Fore, Style
from lark import Lark, Token, Transformer, Discard, ParseError

# dataframe columns
DATE = "date"
SECONDS = "seconds"
DESCRIPTION = "description"

# keywords to look for in descriptions, for categorizing work days
IN_OFFICE = "in office"
WFH = "WFH"
SICK = "sick"
PUBLIC_HOLIDAY = "public holiday"
VACATION = "vacation"
DAY_CATEGORIES = (IN_OFFICE, WFH, SICK, PUBLIC_HOLIDAY, VACATION)


class WorkingHoursTransformer(Transformer):
    def WHITESPACE(self, tok: Token):
        return Discard

    def NEWLINE(self, tok: Token):
        return Discard

    @staticmethod
    def _parse_datetime(date_str: str) -> datetime.datetime:
        if "-" in date_str:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d")
        elif "/" in date_str:
            return datetime.datetime.strptime(date_str, "%m/%d/%Y")
        elif "." in date_str:
            return datetime.datetime.strptime(date_str, "%d.%m.%Y")
        else:
            raise ValueError

    @staticmethod
    def _parse_time(time_str: str) -> datetime.time:
        num_colons = sum(1 for c in time_str if c == ":")
        if num_colons == 2:
            pattern = "%H:%M:%S"
        elif num_colons == 1:
            pattern = "%H:%M"
        else:
            raise ValueError
        return datetime.datetime.strptime(time_str, pattern).time()

    def DATE(self, tok: Token):
        try:
            return self._parse_datetime(tok.value)
        except ValueError:
            raise ParseError(
                f"Invalid date '{tok.value}' in line {tok.line}, col {tok.column}"
            )

    def TIME(self, tok: Token):
        try:
            return self._parse_time(tok.value)
        except ValueError:
            raise ParseError(
                f"Invalid time '{tok.value}' in line {tok.line}, col {tok.column}"
            )

    def DURATION(self, tok: Token):
        duration_str = tok.value
        if not any(c in string.ascii_letters for c in duration_str):
            duration_str += "min"
        try:
            delta = pd.to_timedelta(duration_str)
        except ValueError:
            raise ParseError(
                f"Invalid duration '{duration_str}' in line {tok.line}, col {tok.column}."
            )
        return delta

    def SIGN(self, tok: Token):
        return -1 if tok in ("-", "minus") else 1

    def time_interval(self, args):
        start, end = args
        if end <= start:
            raise ParseError(
                f"Invalid time interval in line {args.meta.line}, col {args.meta.column}: end > start must hold, but got {end=}, {start=}."
            )
        delta = datetime.datetime.combine(
            datetime.date.min, end
        ) - datetime.datetime.combine(datetime.date.min, start)
        return delta

    def time_delta(self, args):
        return args[0]

    def signed_time_delta(self, args):
        if len(args) == 1:
            sign, duration = 1, args[0]
        elif len(args) == 2:
            sign, duration = args
        else:
            raise NotImplementedError
        return sign * duration

    def description(self, args):
        return "".join(tok.value for tok in args)

    def secondary_line(self, args):
        if len(args) == 1:
            return args[0], None
        elif len(args) == 2:
            return tuple(args)
        else:
            raise NotImplementedError

    def primary_line(self, args):
        if len(args) == 2:
            return *args, None
        elif len(args) == 3:
            return tuple(args)
        else:
            raise NotImplementedError

    def workday(self, args):
        periods = []
        date = None
        for period in args:
            if date is None:
                date, duration, description = period
            else:
                duration, description = period
            p = {DATE: date, SECONDS: int(duration.total_seconds())}
            if description:
                p[DESCRIPTION] = description
            periods.append(p)
        return periods

    def description_day(self, args):
        date, description = args
        return [{DATE: date, SECONDS: None, DESCRIPTION: description}]

    def start(self, args):
        flattened = [period for periods in args for period in periods]
        return pd.DataFrame(flattened)


def parse(path: pathlib.Path) -> pd.DataFrame:
    grammar_path = pathlib.Path(__file__).parent / "working_hours.lark"
    with grammar_path.open() as f_grammar, path.open() as f_input:
        lark = Lark(f_grammar, propagate_positions=True)
        times = f_input.read()

    tree = lark.parse(times)
    df = WorkingHoursTransformer().transform(tree)
    return df


def to_csv(df: pd.DataFrame) -> None:
    csv = df.to_csv(index=False)
    print(csv)


def cumulative_delta(
    df: pd.DataFrame,
    days_categorized: pd.Series,
    working_hours: float = 8.0,
    daily_break_hours: float = 0.5,
) -> None:
    """
    Compute cumulative delta in hours.
    """
    # drop vacation / public holiday days
    working_days = days_categorized.isin((IN_OFFICE, WFH))
    df = df.loc[df[DATE].isin(working_days.index[working_days])]

    df = df.sort_values(DATE)
    hours_per_day = df.groupby(DATE)[SECONDS].sum() / 3600
    delta_per_day = hours_per_day - (working_hours + daily_break_hours)
    cumu_delta = delta_per_day.cumsum()

    # make it look nice
    cumu_delta_str = cumu_delta.map(lambda d: f"{d:+.2f}")
    is_below_delta = cumu_delta < 0
    cumu_delta_str.loc[is_below_delta] = (
        Fore.RED + Style.BRIGHT + cumu_delta_str.loc[is_below_delta] + Style.RESET_ALL
    )
    cumu_delta_str.loc[~is_below_delta] = (
        Fore.GREEN
        + Style.BRIGHT
        + cumu_delta_str.loc[~is_below_delta]
        + Style.RESET_ALL
    )
    df_str = cumu_delta_str.to_csv(sep="\t", header=False).strip()
    print(df_str)


def count_categories(days_categorized: pd.Series) -> None:
    """
    Count and print the number of days per category, per year.
    """
    for year, df in days_categorized.groupby(days_categorized.index.year):
        counts = df.value_counts()
        counts["total"] = counts.sum()
        counts_str = counts.to_csv(sep="\t", header=False)
        print(f"{year}:\n{counts_str}")


def categorize_days(df: pd.DataFrame) -> pd.Series:
    """
    Categorize days based on keywords in log descriptions.
    """
    days_categorized = pd.Series(IN_OFFICE, index=df[DATE].unique())
    grouper = df.groupby(DATE)[DESCRIPTION]
    for keyword in DAY_CATEGORIES:
        is_of_category = grouper.apply(
            lambda d: any(
                keyword in description
                for description in d.values
                if pd.notna(description)
            )
        )
        days_categorized.loc[is_of_category] = keyword
    return days_categorized


def run():
    parser = argparse.ArgumentParser(description="Creates reports from plaintext logs of working hours.")
    parser.add_argument(
        "filename", help="Plaintext file with working times", type=pathlib.Path
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--csv", help="Parse file and print CSV", action="store_true")
    group.add_argument(
        "-d",
        "--delta",
        help="Print cumulative delta (default action)",
        action="store_true",
    )
    group.add_argument(
        "-c", "--count", help="Count in-office, WFH, etc. days", action="store_true"
    )
    parser.add_argument(
        "-w",
        "--working-hours",
        help="Working hours per day (default: 8.0), only used with the '--delta' option.",
        type=float,
        default=8.0,
    )
    parser.add_argument(
        "-b",
        "--daily-break-hours",
        help="Hours of break to subtract from each working day (default: 0.5), only used with the '--delta' option.",
        type=float,
        default=0.5,
    )

    args = parser.parse_args()

    df = parse(args.filename)
    if args.csv:
        to_csv(df)
    else:
        days_categorized = categorize_days(df)
        if args.count:
            count_categories(days_categorized)
        else:
            cumulative_delta(
                df,
                days_categorized,
                working_hours=args.working_hours,
                daily_break_hours=args.daily_break_hours,
            )


if __name__ == "__main__":
    run()
