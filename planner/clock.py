"""Clock times, dates and time intervals. Times of day are minutes after midnight."""

from __future__ import annotations

from datetime import date, timedelta


def hm(minutes: int) -> str:
    """Minutes after midnight -> "HH:MM"."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def dur(minutes: int) -> str:
    """Minutes -> "4h05"."""
    return f"{minutes // 60}h{minutes % 60:02d}"


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def merge_intervals(intervals) -> list[tuple[int, int]]:
    """Sort (start, end) pairs and merge the ones that overlap or touch."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def half_hours(minutes: float) -> int:
    """Round to the nearest half hour; exact halfway points go up."""
    return int(minutes / 30 + 0.5) * 30
