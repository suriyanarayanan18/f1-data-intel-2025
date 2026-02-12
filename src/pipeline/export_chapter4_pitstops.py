"""Generate Chapter 4 pit-stop intelligence export for 2025."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import fastf1
import pandas as pd

from src.utils.config import EXPORTS_DIR, FASTF1_CACHE_DIR

TARGET_YEAR = 2025
OPENF1_BASE = "https://api.openf1.org/v1"
OUT_PATH = EXPORTS_DIR / "ch4_pitstops.json"


def _openf1_get(endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    query = ""
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        query = "?" + urlencode(clean)

    url = f"{OPENF1_BASE}{endpoint}{query}"
    with urlopen(url, timeout=60) as response:  # noqa: S310 - trusted API URL
        return json.load(response)


def _safe_timestamp(value: Any) -> pd.Timestamp | pd.NaT:
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return pd.NaT
    return ts


def _timestamp_to_date(value: Any) -> str | None:
    ts = _safe_timestamp(value)
    if pd.isna(ts):
        ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _fetch_openf1_race_sessions() -> pd.DataFrame:
    sessions = _openf1_get("/sessions", {"year": TARGET_YEAR, "session_name": "Race"})
    df = pd.DataFrame(sessions)
    if df.empty:
        raise ValueError("OpenF1 /sessions returned no 2025 race sessions.")

    required = ["session_key", "session_name", "date_start"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"OpenF1 sessions missing required columns: {missing}")

    df = df[df["session_name"].astype(str).str.lower() == "race"].copy()
    df["session_key"] = pd.to_numeric(df["session_key"], errors="coerce")
    df = df.dropna(subset=["session_key"])
    df["session_key"] = df["session_key"].astype(int)
    df["date_start_ts"] = df["date_start"].map(_safe_timestamp)
    df = df.sort_values("date_start_ts").drop_duplicates(subset=["session_key"], keep="first")
    return df


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
    df = df[df["RoundNumber"] > 0]
    df = df.copy()
    df["EventDateTs"] = pd.to_datetime(df["EventDate"], errors="coerce", utc=True)
    df = df.sort_values("RoundNumber").drop_duplicates(subset=["RoundNumber"], keep="first")
    return df


def _resolve_rounds_with_sessions() -> list[dict[str, Any]]:
    session_df = _fetch_openf1_race_sessions()
    schedule_df = _fetch_schedule_rounds()

    session_df = session_df.reset_index(drop=True)
    schedule_df = schedule_df.reset_index(drop=True)

    rounds: list[dict[str, Any]] = []
    count = min(len(schedule_df), len(session_df))

    if count == 0:
        return rounds

    for idx in range(count):
        sch = schedule_df.iloc[idx]
        ses = session_df.iloc[idx]
        rounds.append(
            {
                "round": int(sch["RoundNumber"]),
                "event": str(sch["EventName"]),
                "date": _timestamp_to_date(sch["EventDate"]),
                "session_key": int(ses["session_key"]),
            }
        )

    return rounds


def _fetch_openf1_driver_map(session_key: int) -> dict[int, dict[str, str]]:
    records = _openf1_get("/drivers", {"session_key": session_key})
    df = pd.DataFrame(records)
    if df.empty or "driver_number" not in df.columns:
        return {}

    df["driver_number"] = pd.to_numeric(df["driver_number"], errors="coerce")
    df = df.dropna(subset=["driver_number"])
    df["driver_number"] = df["driver_number"].astype(int)

    mapping: dict[int, dict[str, str]] = {}
    for row in df.itertuples(index=False):
        driver_number = int(getattr(row, "driver_number"))
        abbr = str(getattr(row, "name_acronym", "") or "").strip()
        team = str(getattr(row, "team_name", "") or "").strip()
        full_name = str(getattr(row, "full_name", "") or "").strip()
        if driver_number not in mapping:
            mapping[driver_number] = {
                "abbr": abbr,
                "team": team,
                "name": full_name,
            }

    return mapping


def _fetch_fastf1_driver_map(round_number: int) -> dict[int, dict[str, str]]:
    mapping: dict[int, dict[str, str]] = {}
    try:
        session = fastf1.get_session(TARGET_YEAR, round_number, "R")
        session.load(laps=False, telemetry=False, weather=False, messages=False)
    except Exception:
        return mapping

    results = session.results
    if results is None or results.empty:
        return mapping

    required = ["DriverNumber", "Abbreviation", "TeamName"]
    missing = [c for c in required if c not in results.columns]
    if missing:
        return mapping

    for row in results.itertuples(index=False):
        driver_number = pd.to_numeric(getattr(row, "DriverNumber", None), errors="coerce")
        if pd.isna(driver_number):
            continue
        mapping[int(driver_number)] = {
            "abbr": str(getattr(row, "Abbreviation", "") or "").strip(),
            "team": str(getattr(row, "TeamName", "") or "").strip(),
            "name": str(getattr(row, "FullName", "") or "").strip(),
        }

    return mapping


def _fetch_pit_df(session_key: int) -> pd.DataFrame:
    records = _openf1_get("/pit", {"session_key": session_key})
    pit_df = pd.DataFrame(records)
    if pit_df.empty:
        return pit_df

    duration_col = None
    for candidate in ["pit_duration", "stop_duration", "pit_time"]:
        if candidate in pit_df.columns:
            duration_col = candidate
            break

    if duration_col is None:
        return pd.DataFrame()

    pit_df = pit_df.copy()
    pit_df["pit_s"] = pd.to_numeric(pit_df[duration_col], errors="coerce")
    pit_df = pit_df[pit_df["pit_s"].notna()].copy()
    pit_df = pit_df[(pit_df["pit_s"] > 0) & (pit_df["pit_s"] < 120)].copy()
    pit_df["driver_number"] = pd.to_numeric(pit_df.get("driver_number"), errors="coerce")
    pit_df = pit_df.dropna(subset=["driver_number"])
    pit_df["driver_number"] = pit_df["driver_number"].astype(int)
    pit_df["lap_number"] = pd.to_numeric(pit_df.get("lap_number"), errors="coerce")
    return pit_df


def _fetch_fastf1_pit_df(round_number: int) -> pd.DataFrame:
    """Fallback pit-stop extraction from FastF1 laps when OpenF1 /pit is empty."""
    try:
        session = fastf1.get_session(TARGET_YEAR, round_number, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
    except Exception:
        return pd.DataFrame()

    laps = session.laps
    if laps is None or laps.empty:
        return pd.DataFrame()

    laps_df = laps.copy()
    required = ["Driver", "LapNumber", "PitInTime", "PitOutTime"]
    if any(col not in laps_df.columns for col in required):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for driver, grp in laps_df.groupby("Driver"):
        grp = grp.sort_values("LapNumber")
        lap_index = {int(pd.to_numeric(row.LapNumber, errors="coerce")): row for row in grp.itertuples(index=False)}

        for row in grp.itertuples(index=False):
            lap_number = pd.to_numeric(getattr(row, "LapNumber", None), errors="coerce")
            if pd.isna(lap_number):
                continue
            lap_number = int(lap_number)

            pit_out = pd.to_timedelta(getattr(row, "PitOutTime", None), errors="coerce")
            if pd.isna(pit_out):
                continue

            prev_row = lap_index.get(lap_number - 1)
            if prev_row is None:
                continue

            pit_in = pd.to_timedelta(getattr(prev_row, "PitInTime", None), errors="coerce")
            if pd.isna(pit_in):
                continue

            pit_s = float((pit_out - pit_in).total_seconds())
            if not (0 < pit_s < 120):
                continue

            rows.append(
                {
                    "driver_number": pd.to_numeric(getattr(row, "DriverNumber", None), errors="coerce"),
                    "driver": str(driver),
                    "team": str(getattr(row, "Team", "") or ""),
                    "lap_number": lap_number,
                    "pit_s": pit_s,
                }
            )

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    out["driver_number"] = pd.to_numeric(out["driver_number"], errors="coerce")
    return out


def _team_round_metrics(round_number: int, pit_df: pd.DataFrame) -> list[dict[str, Any]]:
    if pit_df.empty:
        return []

    rows: list[dict[str, Any]] = []
    grouped = pit_df.groupby("team", dropna=False)

    for team, grp in grouped:
        if not isinstance(team, str) or not team.strip():
            continue
        values = grp["pit_s"].astype(float)
        rows.append(
            {
                "round": round_number,
                "team": team,
                "avg_pit_s": round(float(values.mean()), 3),
                "p25_pit_s": round(float(values.quantile(0.25)), 3),
                "p50_pit_s": round(float(values.quantile(0.50)), 3),
                "p75_pit_s": round(float(values.quantile(0.75)), 3),
                "best_pit_s": round(float(values.min()), 3),
                "consistency_s": round(float(values.std(ddof=0)), 3),
                "n_stops": int(len(values)),
            }
        )

    rows.sort(key=lambda x: (x["avg_pit_s"], x["team"]))
    return rows


def _race_summary_row(round_number: int, pit_df: pd.DataFrame) -> dict[str, Any] | None:
    if pit_df.empty:
        return None

    values = pit_df["pit_s"].astype(float)
    q1 = float(values.quantile(0.25))
    q3 = float(values.quantile(0.75))

    fastest_row = pit_df.loc[pit_df["pit_s"].idxmin()]

    return {
        "round": round_number,
        "total_stops": int(len(values)),
        "median_pit_s": round(float(values.median()), 3),
        "iqr_pit_s": round(q3 - q1, 3),
        "fastest_pit_s": round(float(fastest_row["pit_s"]), 3),
        "fastest_team": str(fastest_row.get("team", "")),
        "fastest_driver": str(fastest_row.get("driver", "")),
    }


def _compute_undercut_from_openf1(session_key: int, pit_df: pd.DataFrame) -> tuple[dict[str, tuple[int, int]] | None, str]:
    """Return per-team (successes, attempts) from position changes around pit laps."""
    if pit_df.empty:
        return {}, "No pit stops for undercut proxy."

    records = _openf1_get("/position", {"session_key": session_key})
    pos_df = pd.DataFrame(records)
    if pos_df.empty:
        return None, "OpenF1 /position returned no data; undercut proxy unavailable."

    required = ["driver_number", "position", "lap_number"]
    missing = [c for c in required if c not in pos_df.columns]
    if missing:
        return None, f"OpenF1 /position missing required columns {missing}; undercut proxy unavailable."

    pos_df = pos_df.copy()
    pos_df["driver_number"] = pd.to_numeric(pos_df["driver_number"], errors="coerce")
    pos_df["position"] = pd.to_numeric(pos_df["position"], errors="coerce")
    pos_df["lap_number"] = pd.to_numeric(pos_df["lap_number"], errors="coerce")
    pos_df = pos_df.dropna(subset=["driver_number", "position", "lap_number"])
    if pos_df.empty:
        return None, "OpenF1 /position had no usable lap-number rows; undercut proxy unavailable."

    pos_df["driver_number"] = pos_df["driver_number"].astype(int)
    pos_df["position"] = pos_df["position"].astype(int)
    pos_df["lap_number"] = pos_df["lap_number"].astype(int)

    index: dict[tuple[int, int], int] = {}
    for row in pos_df.itertuples(index=False):
        key = (int(row.driver_number), int(row.lap_number))
        index[key] = int(row.position)

    outcomes: dict[str, list[int]] = defaultdict(list)
    for row in pit_df.itertuples(index=False):
        if pd.isna(row.lap_number):
            continue

        driver_number = int(row.driver_number)
        pit_lap = int(row.lap_number)
        team = str(row.team)

        before = index.get((driver_number, pit_lap - 1))
        if before is None:
            continue

        after_positions = [index.get((driver_number, pit_lap + d)) for d in (1, 2, 3)]
        after_candidates = [p for p in after_positions if p is not None]
        if not after_candidates:
            continue

        after = after_candidates[-1]
        gain = before - after
        outcomes[team].append(1 if gain >= 1 else 0)

    result: dict[str, tuple[int, int]] = {}
    for team, vals in outcomes.items():
        result[team] = (int(sum(vals)), int(len(vals)))

    return result, "Undercut proxy uses position change from lap before pit to best available reading within next 3 laps."


def main() -> None:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(FASTF1_CACHE_DIR))

    rounds = _resolve_rounds_with_sessions()

    team_by_round: list[dict[str, Any]] = []
    race_summary: list[dict[str, Any]] = []
    season_pit_rows: list[pd.DataFrame] = []
    undercut_acc: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    undercut_note = "Undercut proxy unavailable."
    fallback_rounds = 0

    for round_info in rounds:
        round_number = int(round_info["round"])
        session_key = int(round_info["session_key"])

        pit_df = _fetch_pit_df(session_key)
        used_fallback = False
        if pit_df.empty:
            pit_df = _fetch_fastf1_pit_df(round_number)
            used_fallback = True
        if pit_df.empty:
            continue
        if used_fallback:
            fallback_rounds += 1

        openf1_map = _fetch_openf1_driver_map(session_key)
        fastf1_map = _fetch_fastf1_driver_map(round_number)

        def map_driver_meta(driver_number: int) -> tuple[str, str]:
            o = openf1_map.get(driver_number, {})
            f = fastf1_map.get(driver_number, {})
            driver = str(o.get("abbr") or f.get("abbr") or driver_number)
            team = str(o.get("team") or f.get("team") or "Unknown")
            return driver, team

        mapped = pit_df.copy()
        if "driver" not in mapped.columns:
            mapped["driver"] = ""
        if "team" not in mapped.columns:
            mapped["team"] = ""
        if "driver_number" not in mapped.columns:
            mapped["driver_number"] = pd.NA

        def _fill_row(row: pd.Series) -> pd.Series:
            number = pd.to_numeric(row.get("driver_number"), errors="coerce")
            if pd.notna(number):
                driver, team = map_driver_meta(int(number))
                if not str(row.get("driver", "")).strip():
                    row["driver"] = driver
                if not str(row.get("team", "")).strip():
                    row["team"] = team
            return row

        mapped = mapped.apply(_fill_row, axis=1)
        mapped["driver"] = mapped["driver"].astype(str)
        mapped["team"] = mapped["team"].astype(str)

        season_pit_rows.append(mapped)

        round_team_rows = _team_round_metrics(round_number, mapped)
        team_by_round.extend(round_team_rows)

        summary = _race_summary_row(round_number, mapped)
        if summary is not None:
            race_summary.append(summary)

        undercut_round, note = _compute_undercut_from_openf1(session_key, mapped)
        if undercut_round is not None:
            undercut_note = note
            for team, (succ, att) in undercut_round.items():
                undercut_acc[team][0] += succ
                undercut_acc[team][1] += att

    if season_pit_rows:
        all_pits = pd.concat(season_pit_rows, ignore_index=True)
    else:
        all_pits = pd.DataFrame(columns=["team", "driver", "pit_s"])

    team_season: list[dict[str, Any]] = []
    for team, grp in all_pits.groupby("team", dropna=False):
        if not isinstance(team, str) or not team.strip() or grp.empty:
            continue

        values = grp["pit_s"].astype(float)
        succ, att = undercut_acc.get(team, [0, 0])
        undercut_success = None if att == 0 else round(succ / att, 3)

        team_season.append(
            {
                "team": team,
                "avg_pit_s": round(float(values.mean()), 3),
                "consistency_s": round(float(values.std(ddof=0)), 3),
                "best_pit_s": round(float(values.min()), 3),
                "n_stops": int(len(values)),
                "undercut_success": undercut_success,
            }
        )

    team_season.sort(key=lambda x: (x["avg_pit_s"], x["team"]))
    race_summary.sort(key=lambda x: x["round"])
    team_by_round.sort(key=lambda x: (x["round"], x["avg_pit_s"], x["team"]))

    teams = sorted({row["team"] for row in team_season})

    payload = {
        "rounds": rounds,
        "teams": teams,
        "team_season": team_season,
        "team_by_round": team_by_round,
        "race_summary": race_summary,
        "notes": {
            "undercut_method": undercut_note,
            "data_source": (
                "OpenF1 (FastF1 fallback for mapping and missing pit rows)"
                if fallback_rounds > 0
                else "OpenF1 (FastF1 fallback for mapping)"
            ),
        },
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    total_stops = int(len(all_pits))
    print(f"rounds processed: {len(race_summary)}")
    print(f"total stops: {total_stops}")
    print(f"output path: {OUT_PATH}")


if __name__ == "__main__":
    main()
