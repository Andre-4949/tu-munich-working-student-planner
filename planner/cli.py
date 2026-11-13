"""Plan the working-student days from a TUMonline export and a config.toml."""

from __future__ import annotations

import argparse
import csv
import json
import tomllib
from datetime import date
from pathlib import Path

from planner.config import Config, load_config
from planner.constants import REQUIRED_CSV_COLUMNS
from planner.errors import ConfigError
from planner.events import layout_lanes, mark_skipped
from planner.export import plan_to_json
from planner.pdf import compile_pdf
from planner.planning import Plan, build_plan
from planner.summary import print_summary
from planner.supervisor import write_boss_csv
from planner.tumonline import convert

SUPERVISOR_PDF_INPUTS = {"audience": "boss", "views": "month", "title": "Office hours"}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = _load_config(parser, args.config)
    events = _read_export(parser, args.csv)
    first, last = _planning_range(events, config)
    events = [e for e in events if first.isoformat() <= e["date"] <= last.isoformat()]
    if not events:
        parser.error(f"no sessions between {first} and {last}; check the calendar range in the config")

    mark_skipped(events, config)
    layout_lanes(events)
    plan = build_plan(events, config, first, last)
    _write_outputs(parser, args, events, plan, config)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="CSV file exported from TUMonline")
    parser.add_argument("--config", type=Path, default=Path("config.toml"),
                        help="config file (default: config.toml; start from config.example.toml)")
    parser.add_argument("-o", "--output", type=Path, default=Path("data/plan.json"),
                        help="JSON file to write (default: data/plan.json)")
    parser.add_argument("--compile", action="store_true",
                        help="afterwards run 'typst compile calendar.typ plan.pdf' on the JSON")
    parser.add_argument("--boss-csv", nargs="?", type=Path, const=Path("data/office-hours.csv"),
                        metavar="PATH",
                        help="also write a short CSV for your supervisor: office days, rough start, "
                             "work hours and exam days (default path: data/office-hours.csv)")
    parser.add_argument("--boss-pdf", nargs="?", type=Path, const=Path("data/office-hours.pdf"),
                        metavar="PATH",
                        help="also write a supervisor PDF: the monthly view with only the office "
                             "times and exam days (default path: data/office-hours.pdf)")
    return parser


def _load_config(parser: argparse.ArgumentParser, path: Path) -> Config:
    try:
        return load_config(path)
    except FileNotFoundError:
        parser.error(f"config file {path} not found (copy config.example.toml to config.toml and adapt it)")
    except (ConfigError, tomllib.TOMLDecodeError) as exc:
        parser.error(f"{path}: {exc}")


def _read_export(parser: argparse.ArgumentParser, path: Path) -> list[dict]:
    # utf-8-sig strips the byte-order mark that TUMonline puts at the start.
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_CSV_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            parser.error(f"{path} does not look like a TUMonline export "
                         f"(missing columns: {', '.join(missing)}). "
                         "Make sure the export language is German.")
        events = convert(list(reader))
    if not events:
        parser.error("no usable sessions found in the CSV")
    return events


def _planning_range(events: list[dict], config: Config) -> tuple[date, date]:
    """The calendar range from the config, or the first and last session of the export."""
    first = config.calendar_start or date.fromisoformat(events[0]["date"])
    last = config.calendar_end or date.fromisoformat(events[-1]["date"])
    return first, last


def _write_outputs(parser: argparse.ArgumentParser, args: argparse.Namespace,
                   events: list[dict], plan: Plan, config: Config) -> None:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = plan_to_json(events, plan, config)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print_summary(events, plan, config)
    print(f"\nwrote {args.output}")
    if args.boss_csv:
        write_boss_csv(plan, config, args.boss_csv)
        print(f"wrote {args.boss_csv}")
    if args.boss_pdf:
        _compile_or_exit(parser, args.output, args.boss_pdf, SUPERVISOR_PDF_INPUTS)
    if args.compile:
        _compile_or_exit(parser, args.output)


def _compile_or_exit(parser: argparse.ArgumentParser, json_path: Path, pdf_path: Path | None = None,
                     inputs: dict[str, str] | None = None) -> None:
    try:
        pdf = compile_pdf(json_path, pdf_path, extra_inputs=inputs)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"wrote {pdf}")
