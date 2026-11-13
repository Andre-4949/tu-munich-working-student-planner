"""Session bookkeeping: skipped sessions, and the lanes that place overlapping sessions side by side."""

from __future__ import annotations


from planner.config import Config
from planner.tumonline import normalize_lv


def assign_lanes(events: list[dict]) -> None:
    """Give overlapping events of the same day side-by-side lanes (in place).

    Adds `lane` (0-based column) and `lanes` (number of columns in the overlap cluster).
    """
    by_day: dict[str, list[dict]] = {}
    for event in events:
        by_day.setdefault(event["date"], []).append(event)

    for day_events in by_day.values():
        day_events.sort(key=lambda e: (e["start_min"], e["end_min"]))
        cluster: list[dict] = []
        lane_ends: list[int] = []
        cluster_end = -1

        def close_cluster() -> None:
            for member in cluster:
                member["lanes"] = max(len(lane_ends), 1)

        for event in day_events:
            if cluster and event["start_min"] >= cluster_end:
                close_cluster()
                cluster, lane_ends, cluster_end = [], [], -1
            for lane, end in enumerate(lane_ends):
                if end <= event["start_min"]:
                    lane_ends[lane] = event["end_min"]
                    event["lane"] = lane
                    break
            else:
                event["lane"] = len(lane_ends)
                lane_ends.append(event["end_min"])
            cluster.append(event)
            cluster_end = max(cluster_end, event["end_min"])
        close_cluster()


def mark_skipped(events: list[dict], config: Config) -> None:
    """Flag the sessions the user does not attend (in place)."""
    for event in events:
        lv = normalize_lv(event["lv_number"])
        event["skipped"] = bool(lv) and (
            lv in config.not_attended or (lv, event["type"].upper()) in config.sessions_not_attended
        )


def layout_lanes(events: list[dict]) -> None:
    """Lanes for the attended sessions only (in place).

    Skipped sessions do not take a lane: they are drawn as a narrow strip on top,
    so they never squeeze the sessions the user really attends.
    """
    for event in events:
        event["lane"], event["lanes"] = 0, 1
    assign_lanes([e for e in events if not e["skipped"]])
