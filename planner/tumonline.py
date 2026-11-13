"""Reading a TUMonline export: rows become sessions with clock times in minutes."""

from __future__ import annotations

import re
import sys
from datetime import datetime


# A "module code" like IN2005, MA3305 or CSE... (used to strip clutter from titles).
_CODE = re.compile(r"^[A-Z]{2,4}\d{3,5}$")


# "<room code>, <room name> (<TUM building id>)", e.g. "01.02.003, Lecture Hall B (9999.EG.003)"
_ROOM = re.compile(r"^(?P<code>[^,]+),\s*(?P<name>.*?)\s*(?:\((?P<id>\d{4}\.[\w.]+)\))?$")


def normalize_lv(number: str) -> str:
    """TUMonline writes LV numbers with leading zeros ("0000000101"); "101" is the same course."""
    return number.strip().lstrip("0")


def squash_spaces(text: str) -> str:
    """Collapse runs of whitespace (the export contains double spaces)."""
    return re.sub(r"\s+", " ", text).strip()


def short_title(title: str) -> str:
    """Drop module-code groups such as '[MA3305, IN2156]' or '(IN2005)' from a title."""

    def strip_if_codes(match: re.Match[str]) -> str:
        items = [item.strip() for item in match.group(1).split(",")]
        return "" if all(_CODE.match(item) for item in items) else match.group(0)

    title = re.sub(r"\s*\[([^\]]*)\]", strip_if_codes, title)
    title = re.sub(r"\s*\(([^)]*)\)", strip_if_codes, title)
    return squash_spaces(title)


def parse_room(raw: str) -> dict[str, str]:
    """Split a TUMonline location string into name, room code and building id."""
    raw = squash_spaces(raw)
    match = _ROOM.match(raw)
    if not raw or not match:
        return {"room": raw, "room_code": "", "room_id": ""}
    return {
        "room": match.group("name") or match.group("code"),
        "room_code": match.group("code").strip(),
        "room_id": match.group("id") or "",
    }


def minutes_of_clock(clock: str) -> int:
    hours, minutes = clock.split(":")[:2]
    return int(hours) * 60 + int(minutes)


def convert(rows: list[dict[str, str]]) -> list[dict]:
    """TUMonline CSV rows -> event dicts (sorted and de-duplicated; lanes are set later)."""
    events: list[dict] = []
    seen: set[tuple] = set()

    for number, row in enumerate(rows, start=2):  # line 1 is the header
        start, end = (row.get("VON") or "").strip(), (row.get("BIS") or "").strip()
        if not start or not end:
            print(f"warning: line {number}: no start/end time, skipped "
                  f"({row.get('TITEL', '?')!r})", file=sys.stderr)
            continue
        try:
            day = datetime.strptime(row["DATUM"].strip(), "%d.%m.%Y").date()
        except ValueError:
            print(f"warning: line {number}: unreadable date {row['DATUM']!r}, skipped",
                  file=sys.stderr)
            continue

        full_title = squash_spaces(row["TITEL"])
        event = {
            "date": day.isoformat(),
            "start": start[:5],
            "end": end[:5],
            "start_min": minutes_of_clock(start),
            "end_min": minutes_of_clock(end),
            "lv_number": (row.get("LV_NUMMER") or "").strip(),
            "title": short_title(full_title),
            "full_title": full_title,
            "type": (row.get("LV_ART") or "").strip(),
            "group": squash_spaces(row.get("LV_GRUPPE") or ""),
            "kind": (row.get("EREIGNIS_TYP") or "").strip(),
            **parse_room(row.get("ORT") or ""),
        }
        key = (event["date"], event["start"], event["end"], event["lv_number"],
               event["title"], event["group"])
        if key in seen:
            continue
        seen.add(key)
        events.append(event)

    events.sort(key=lambda e: (e["date"], e["start_min"], e["end_min"], e["title"]))
    return events
