"""Generate Chapter 5 overtaking export for 2025 race sessions."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import fastf1
import pandas as pd

from src.utils.config import EXPORTS_DIR, FASTF1_CACHE_DIR

TARGET_YEAR = 2025
OPENF1_BASE = "https://api.openf1.org/v1"
OUT_PATH = EXPORTS_DIR / "ch5_overtakes.json"
PASS_COOLDOWN_S = 8.0


def _openf1_get(endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    query = ""
    if params:
        query = "?" + urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{OPENF1_BASE}{endpoint}{query}"
    with urlopen(url, timeout=90) as response:  # noqa: S310 - fixed trusted endpoint
        return json.load(response)


def _safe_ts(value: Any) -> pd.Timestamp | pd.NaT:
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts


def _to_date_str(value: Any) -> str | None:
    ts = _safe_ts(value)
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _fetch_openf1_races() -> pd.DataFrame:
    records = _openf1_get("/sessions", {"year": TARGET_YEAR, "session_name": "Race"})
    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("OpenF1 /sessions returned no 2025 race sessions.")

    required = ["session_key", "session_name", "date_start"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"OpenF1 sessions missing required columns: {missing}")

    race_df = df[df["session_name"].astype(str).str.lower() == "race"].copy()
    race_df["session_key"] = pd.to_numeric(race_df["session_key"], errors="coerce")
    race_df = race_df.dropna(subset=["session_key"])
    race_df["session_key"] = race_df["session_key"].astype(int)
    race_df["date_start_ts"] = race_df["date_start"].map(_safe_ts)
    race_df = race_df.sort_values("date_start_ts").drop_duplicates(subset=["session_key"], keep="first")
    return race_df


def _fetch_schedule_rounds() -> pd.DataFrame:
    schedule = fastf1.get_event_schedule(TARGET_YEAR)
    if not isinstance(schedule, pd.DataFrame):
        schedule = pd.DataFrame(schedule)

    required = ["RoundNumber", "EventName", "EventDate"]
    missing = [c for c in required if c not in schedule.columns]
    if missing:
        raise ValueError(f"FastF1 schedule missing required columns: {missing}")

    df = schedule.copy()
    df["RoundNumber"] = pd.to_numeric(df["RoundNumber"], errors="coerce")
    df = df.dropna(subset=["RoundNumber"])
    df["RoundNumber"] = df["RoundNumber"].astype(int)
    df = df[df["RoundNumber"] > 0].copy()
    df = df.sort_values("RoundNumber").drop_duplicates(subset=["RoundNumber"], keep="first")
    return df


def _resolve_rounds() -> list[dict[str, Any]]:
    race_df = _fetch_openf1_races().reset_index(drop=True)
    schedule_df = _fetch_schedule_rounds().reset_index(drop=True)

    count = min(len(race_df), len(schedule_df))
    rounds: list[dict[str, Any]] = []

    for idx in range(count):
        sch = schedule_df.iloc[idx]
        ses = race_df.iloc[idx]
        rounds.append(
            {
                "round": int(sch["RoundNumber"]),
                "event": str(sch["EventName"]),
                "date": _to_date_str(sch["EventDate"]),
                "session_key": int(ses["session_key"]),
            }
        )
    return rounds


def _driver_map_openf1(session_key: int) -> dict[int, dict[str, str]]:
    records = _openf1_get("/drivers", {"session_key": session_key})
    df = pd.DataFrame(records)
    if df.empty or "driver_number" not in df.columns:
        return {}

    df["driver_number"] = pd.to_numeric(df["driver_number"], errors="coerce")
    df = df.dropna(subset=["driver_number"])
    df["driver_number"] = df["driver_number"].astype(int)

    out: dict[int, dict[str, str]] = {}
    for row in df.itertuples(index=False):
        number = int(getattr(row, "driver_number"))
        if number not in out:
            out[number] = {
                "driver": str(getattr(row, "name_acronym", "") or "").strip(),
                "team": str(getattr(row, "team_name", "") or "").strip(),
            }
    return out


def _driver_map_fastf1(round_number: int) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    try:
        session = fastf1.get_session(TARGET_YEAR, round_number, "R")
        session.load(laps=False, telemetry=False, weather=False, messages=False)
    except Exception:
        return out

    results = session.results
    if results is None or results.empty:
        return out

    required = ["DriverNumber", "Abbreviation", "TeamName"]
    if any(col not in results.columns for col in required):
        return out

    for row in results.itertuples(index=False):
        number = pd.to_numeric(getattr(row, "DriverNumber", None), errors="coerce")
        if pd.isna(number):
            continue
        out[int(number)] = {
            "driver": str(getattr(row, "Abbreviation", "") or "").strip(),
            "team": str(getattr(row, "TeamName", "") or "").strip(),
        }
    return out


def _fetch_position_df(session_key: int) -> pd.DataFrame:
    records = _openf1_get("/position", {"session_key": session_key})
    df = pd.DataFrame(records)
    if df.empty:
        return df

    required = ["driver_number", "position", "date"]
    if any(col not in df.columns for col in required):
        return pd.DataFrame()

    df["driver_number"] = pd.to_numeric(df["driver_number"], errors="coerce")
    df["position"] = pd.to_numeric(df["position"], errors="coerce")
    df["lap_number"] = pd.to_numeric(df.get("lap_number"), errors="coerce")
    df["date_ts"] = df["date"].map(_safe_ts)
    df = df.dropna(subset=["driver_number", "position", "date_ts"]).copy()
    if df.empty:
        return df

    df["driver_number"] = df["driver_number"].astype(int)
    df["position"] = df["position"].astype(int)
    return df.sort_values(["driver_number", "date_ts"])


def _fetch_car_drs_df(session_key: int) -> pd.DataFrame:
    records = _openf1_get("/car_data", {"session_key": session_key})
    df = pd.DataFrame(records)
    if df.empty:
        return df

    drs_col = None
    for candidate in ["drs", "drs_open"]:
        if candidate in df.columns:
            drs_col = candidate
            break
    if drs_col is None:
        return pd.DataFrame()

    if "driver_number" not in df.columns or "date" not in df.columns:
        return pd.DataFrame()

    df["driver_number"] = pd.to_numeric(df["driver_number"], errors="coerce")
    df["drs_flag"] = pd.to_numeric(df[drs_col], errors="coerce")
    df["date_ts"] = df["date"].map(_safe_ts)
    df = df.dropna(subset=["driver_number", "drs_flag", "date_ts"]).copy()
    if df.empty:
        return df

    df["driver_number"] = df["driver_number"].astype(int)
    df = df[df["drs_flag"] > 0].copy()
    return df.sort_values(["driver_number", "date_ts"])


def _infer_passes(position_df: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[int, dict[str, int]]]:
    """Infer pass events from position gains with cooldown de-duplication."""
    events: list[dict[str, Any]] = []
    driver_stats: dict[int, dict[str, int]] = {}

    for driver_number, grp in position_df.groupby("driver_number"):
        grp = grp.sort_values("date_ts")
        if grp.empty:
            continue

        first_pos = int(grp.iloc[0]["position"])
        last_pos = int(grp.iloc[-1]["position"])
        passes_made = 0
        last_pass_ts = pd.NaT
        prev_pos: int | None = None

        for row in grp.itertuples(index=False):
            pos = int(row.position)
            ts = row.date_ts
            if prev_pos is None:
                prev_pos = pos
                continue

            gain = prev_pos - pos
            if gain >= 1:
                cooldown_ok = pd.isna(last_pass_ts) or float((ts - last_pass_ts).total_seconds()) >= PASS_COOLDOWN_S
                if cooldown_ok:
                    passes_made += gain
                    events.append(
                        {
                            "driver_number": int(driver_number),
                            "date_ts": ts,
                            "passes_gained": int(gain),
                        }
                    )
                    last_pass_ts = ts

            prev_pos = pos

        driver_stats[int(driver_number)] = {
            "passes_made": int(passes_made),
            "positions_gained_net": int(first_pos - last_pos),
        }

    return events, driver_stats


def _laps_completed_total(position_df: pd.DataFrame, round_number: int) -> int:
    if "lap_number" in position_df.columns:
        lap_df = position_df.dropna(subset=["lap_number"]).copy()
        if not lap_df.empty:
            max_laps = lap_df.groupby("driver_number")["lap_number"].max()
            if not max_laps.empty:
                return int(max_laps.sum())

    try:
        session = fastf1.get_session(TARGET_YEAR, round_number, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
    except Exception:
        return 0

    laps = session.laps
    if laps is None or laps.empty or "Driver" not in laps.columns:
        return 0
    return int(laps.groupby("Driver").size().sum())


def _drs_share(pass_events: list[dict[str, Any]], drs_df: pd.DataFrame) -> float | None:
    if not pass_events or drs_df.empty:
        return None

    by_driver: dict[int, list[pd.Timestamp]] = {}
    for driver_number, grp in drs_df.groupby("driver_number"):
        by_driver[int(driver_number)] = list(grp["date_ts"])

    drs_passes = 0
    aligned = 0
    for event in pass_events:
        driver_number = int(event["driver_number"])
        ts = event["date_ts"]
        samples = by_driver.get(driver_number)
        if not samples:
            continue

        aligned += 1
        window_start = ts - pd.Timedelta(seconds=2)
        if any(window_start <= sample <= ts for sample in samples):
            drs_passes += int(event["passes_gained"])

    if aligned == 0:
        return None

    total_passes = sum(int(event["passes_gained"]) for event in pass_events)
    if total_passes == 0:
        return None
    return round(drs_passes / total_passes, 3)


def main() -> None:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(FASTF1_CACHE_DIR))

    rounds = _resolve_rounds()
    races: list[dict[str, Any]] = []
    driver_acc: dict[int, dict[str, int]] = defaultdict(lambda: {"passes_made": 0, "positions_gained_net": 0})
    driver_meta: dict[int, dict[str, str]] = {}
    drs_note = "DRS share proxy from OpenF1 car_data around pass timestamps."
    drs_unavailable = False

    for round_info in rounds:
        round_number = int(round_info["round"])
        session_key = int(round_info["session_key"])

        position_df = _fetch_position_df(session_key)
        if position_df.empty:
            continue

        openf1_map = _driver_map_openf1(session_key)
        fastf1_map = _driver_map_fastf1(round_number)
        merged_meta = {**fastf1_map, **openf1_map}
        for number, meta in merged_meta.items():
            driver_meta[number] = meta

        pass_events, driver_stats = _infer_passes(position_df)
        total_overtakes = int(sum(int(event["passes_gained"]) for event in pass_events))

        laps_total = _laps_completed_total(position_df, round_number)
        pass_rate = 0.0 if laps_total <= 0 else float(total_overtakes / laps_total)

        for number, stats in driver_stats.items():
            driver_acc[number]["passes_made"] += int(stats["passes_made"])
            driver_acc[number]["positions_gained_net"] += int(stats["positions_gained_net"])

        try:
            drs_df = _fetch_car_drs_df(session_key)
            drs_share = _drs_share(pass_events, drs_df)
            if drs_share is None:
                drs_unavailable = True
        except Exception:
            drs_share = None
            drs_unavailable = True

        races.append(
            {
                "round": round_number,
                "event": str(round_info["event"]),
                "date": round_info["date"],
                "session_key": session_key,
                "total_overtakes": total_overtakes,
                "pass_rate": round(pass_rate, 5),
                "drs_share": drs_share,
            }
        )

    races.sort(key=lambda x: x["round"])

    pass_rates = [r["pass_rate"] for r in races]
    if pass_rates:
        rate_min = min(pass_rates)
        rate_max = max(pass_rates)
    else:
        rate_min = 0.0
        rate_max = 0.0

    for row in races:
        if rate_max == rate_min:
            score = 50.0
        else:
            normalized = (row["pass_rate"] - rate_min) / (rate_max - rate_min)
            score = (1.0 - normalized) * 100.0
        row["processional_index"] = int(round(score))

    circuit_index = [
        {
            "event": row["event"],
            "round": row["round"],
            "processional_index": row["processional_index"],
            "pass_rate": row["pass_rate"],
            "total_overtakes": row["total_overtakes"],
        }
        for row in sorted(races, key=lambda x: (-x["processional_index"], x["round"]))
    ]

    driver_passing: list[dict[str, Any]] = []
    for number, stats in driver_acc.items():
        meta = driver_meta.get(number, {})
        driver = str(meta.get("driver") or number)
        team = str(meta.get("team") or "Unknown")
        driver_passing.append(
            {
                "driver": driver,
                "team": team,
                "passes_made": int(stats["passes_made"]),
                "positions_gained_net": int(stats["positions_gained_net"]),
            }
        )
    driver_passing.sort(key=lambda x: (-x["passes_made"], -x["positions_gained_net"], x["driver"]))

    if drs_unavailable:
        drs_note = "DRS share proxy unavailable for some/all races due car_data alignment limits."

    payload = {
        "races": races,
        "circuit_index": circuit_index,
        "driver_passing": driver_passing,
        "notes": {
            "method": "Position time-series pass detection with cooldown; DRS share proxy when available.",
            "drs_note": drs_note,
        },
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"races processed: {len(races)}")
    print(f"total overtakes summed: {sum(int(r['total_overtakes']) for r in races)}")
    print(f"output path: {OUT_PATH}")


if __name__ == "__main__":
    main()
