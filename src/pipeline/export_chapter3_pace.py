"""Generate Chapter 3 race pace export: representative race-lap pace and consistency."""

from __future__ import annotations

import json
from pathlib import Path

import fastf1
import pandas as pd

from src.utils.config import EXPORTS_DIR, FASTF1_CACHE_DIR, PROCESSED_DIR

TARGET_YEAR = 2025
SUPPORTED_SESSIONS_JSON = PROCESSED_DIR / "supported_sessions_2025.json"
OUT_PATH = EXPORTS_DIR / "ch3_pace.json"


def _to_date_str(value: object) -> str | None:
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return None
    return pd.Timestamp(dt).strftime("%Y-%m-%d")


def _load_race_rounds() -> list[dict[str, object]]:
    """Load race rounds from supported sessions, or derive from schedule if missing."""
    rounds: list[dict[str, object]] = []

    if SUPPORTED_SESSIONS_JSON.exists():
        with open(SUPPORTED_SESSIONS_JSON, "r", encoding="utf-8") as f:
            records = json.load(f)

        df = pd.DataFrame(records)
        required = ["RoundNumber", "EventName", "SessionName"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"supported_sessions_2025.json missing columns: {missing}")

        race_df = df.copy()
        race_df["SessionName"] = race_df["SessionName"].astype(str).str.strip().str.lower()
        race_df = race_df[race_df["SessionName"] == "race"]

        race_df["RoundNumber"] = pd.to_numeric(race_df["RoundNumber"], errors="coerce")
        race_df = race_df.dropna(subset=["RoundNumber"])
        race_df["RoundNumber"] = race_df["RoundNumber"].astype(int)
        race_df = race_df[race_df["RoundNumber"] > 0]

        race_df = race_df.sort_values("RoundNumber").drop_duplicates(subset=["RoundNumber"], keep="first")

        for row in race_df.itertuples(index=False):
            date_value = getattr(row, "SessionDate", None)
            if pd.isna(date_value):
                date_value = getattr(row, "EventDate", None)
            rounds.append(
                {
                    "round": int(row.RoundNumber),
                    "event": str(row.EventName),
                    "date": _to_date_str(date_value),
                }
            )

        return rounds

    schedule = fastf1.get_event_schedule(TARGET_YEAR)
    if not isinstance(schedule, pd.DataFrame):
        schedule = pd.DataFrame(schedule)

    required = ["RoundNumber", "EventName", "EventDate"]
    missing = [c for c in required if c not in schedule.columns]
    if missing:
        raise ValueError(f"Schedule missing required columns for fallback: {missing}")

    schedule_df = schedule.copy()
    schedule_df["RoundNumber"] = pd.to_numeric(schedule_df["RoundNumber"], errors="coerce")
    schedule_df = schedule_df.dropna(subset=["RoundNumber"])
    schedule_df["RoundNumber"] = schedule_df["RoundNumber"].astype(int)
    schedule_df = schedule_df[schedule_df["RoundNumber"] > 0]
    schedule_df = schedule_df.sort_values("RoundNumber").drop_duplicates(subset=["RoundNumber"], keep="first")

    for row in schedule_df.itertuples(index=False):
        rounds.append(
            {
                "round": int(row.RoundNumber),
                "event": str(row.EventName),
                "date": _to_date_str(getattr(row, "EventDate", None)),
            }
        )

    return rounds


def _lap_seconds(series: pd.Series) -> pd.Series:
    td = pd.to_timedelta(series, errors="coerce")
    return td.dt.total_seconds()


def _representative_laps(driver_laps: pd.DataFrame) -> pd.DataFrame:
    """Apply representative lap filters for race-pace metrics."""
    df = driver_laps.copy()

    if "LapTime" not in df.columns:
        return pd.DataFrame()

    df["lap_s"] = _lap_seconds(df["LapTime"])
    df = df[df["lap_s"].notna() & (df["lap_s"] > 0)].copy()
    if df.empty:
        return df

    # Inlaps/outlaps and pit-stop heuristics.
    pit_mask = pd.Series(False, index=df.index)
    for col in ["PitInTime", "PitOutTime"]:
        if col in df.columns:
            pit_mask = pit_mask | df[col].notna()

    for col in ["IsPitInLap", "IsPitOutLap"]:
        if col in df.columns:
            pit_mask = pit_mask | df[col].fillna(False).astype(bool)

    df = df[~pit_mask].copy()
    if df.empty:
        return df

    median = float(df["lap_s"].median())
    q1 = float(df["lap_s"].quantile(0.25))
    q3 = float(df["lap_s"].quantile(0.75))
    iqr = q3 - q1
    upper_bound = median + 2.5 * iqr

    return df[df["lap_s"] <= upper_bound].copy()


def _round_driver_rows(session: fastf1.core.Session, round_info: dict[str, object]) -> list[dict[str, object]]:
    laps = session.laps
    if laps is None or laps.empty:
        return []

    laps_df = laps.copy()
    if "Driver" not in laps_df.columns:
        return []

    rows: list[dict[str, object]] = []

    for driver in sorted(laps_df["Driver"].dropna().astype(str).unique()):
        driver_laps = laps_df[laps_df["Driver"].astype(str) == driver].copy()
        rep = _representative_laps(driver_laps)
        if rep.empty:
            continue

        team = None
        for team_col in ["Team", "TeamName"]:
            if team_col in rep.columns:
                team_vals = rep[team_col].dropna().astype(str)
                if not team_vals.empty:
                    team = team_vals.mode().iloc[0]
                    break

        avg_lap_s = float(rep["lap_s"].mean())
        p10_lap_s = float(rep["lap_s"].quantile(0.10))
        consistency_s = float(rep["lap_s"].std(ddof=0))

        rows.append(
            {
                "round": int(round_info["round"]),
                "driver": driver,
                "team": team or "Unknown",
                "avg_lap_s": round(avg_lap_s, 3),
                "p10_lap_s": round(p10_lap_s, 3),
                "consistency_s": round(consistency_s, 3),
            }
        )

    if not rows:
        return []

    best_avg = min(row["avg_lap_s"] for row in rows)
    for row in rows:
        row["pace_delta_to_best_avg_s"] = round(float(row["avg_lap_s"] - best_avg), 3)

    rows.sort(key=lambda x: (x["pace_delta_to_best_avg_s"], x["driver"]))
    return rows


def main() -> None:
    FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    fastf1.Cache.enable_cache(str(FASTF1_CACHE_DIR))

    rounds = _load_race_rounds()

    processed_rounds: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []

    for round_info in rounds:
        round_number = int(round_info["round"])
        event_name = str(round_info["event"])

        try:
            session = fastf1.get_session(TARGET_YEAR, round_number, "R")
            session.load(laps=True, telemetry=False, weather=False, messages=False)
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped round {round_number} ({event_name}): load failed - {exc}")
            continue

        try:
            round_rows = _round_driver_rows(session, round_info)
        except Exception as exc:  # noqa: BLE001
            print(f"Skipped round {round_number} ({event_name}): parse failed - {exc}")
            continue

        if not round_rows:
            print(f"Skipped round {round_number} ({event_name}): no representative laps")
            continue

        processed_rounds.append(
            {
                "round": round_number,
                "event": event_name,
                "date": round_info.get("date"),
            }
        )
        rows.extend(round_rows)

    drivers = sorted({row["driver"] for row in rows})

    payload = {
        "rounds": processed_rounds,
        "drivers": drivers,
        "rows": rows,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"rounds processed: {len(processed_rounds)}")
    print(f"drivers count: {len(drivers)}")
    print(f"output path: {OUT_PATH}")


if __name__ == "__main__":
    main()
