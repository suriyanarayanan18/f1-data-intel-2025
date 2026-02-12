"""Generate Chapter 1 web exports: standings progression and points heatmap."""

from __future__ import annotations

import json

import fastf1
import pandas as pd

from src.utils.config import EXPORTS_DIR, PROCESSED_DIR

INPUT_PATH = PROCESSED_DIR / "supported_sessions_2025.parquet"
STANDINGS_OUT = EXPORTS_DIR / "standings_progression.json"
HEATMAP_OUT = EXPORTS_DIR / "points_heatmap.json"
TARGET_YEAR = 2025


def _get_race_rounds(sessions_df: pd.DataFrame) -> list[tuple[int, str]]:
    """Return unique race rounds as (round_number, event_name) pairs."""
    required_cols = ["RoundNumber", "EventName", "SessionName"]
    missing = [col for col in required_cols if col not in sessions_df.columns]
    if missing:
        raise ValueError(f"Missing required columns in supported sessions input: {missing}")

    race_df = sessions_df.copy()
    race_df["SessionName"] = race_df["SessionName"].astype(str)
    race_df = race_df[race_df["SessionName"].str.strip().str.lower() == "race"]

    if race_df.empty:
        raise ValueError("No 'Race' sessions found in supported sessions input.")

    race_df["RoundNumber"] = pd.to_numeric(race_df["RoundNumber"], errors="coerce")
    race_df = race_df.dropna(subset=["RoundNumber"])
    race_df["RoundNumber"] = race_df["RoundNumber"].astype(int)

    race_df = race_df.sort_values("RoundNumber").drop_duplicates(subset=["RoundNumber"], keep="first")
    return [(int(row.RoundNumber), str(row.EventName)) for row in race_df.itertuples(index=False)]


def _extract_round_points(results_df: pd.DataFrame) -> dict[str, float]:
    """Extract points by driver abbreviation from a race result table."""
    if results_df is None or results_df.empty:
        return {}

    if "Points" not in results_df.columns:
        raise ValueError("Session results missing 'Points' column.")

    driver_col = None
    for candidate in ["Abbreviation", "BroadcastName", "FullName", "DriverNumber"]:
        if candidate in results_df.columns:
            driver_col = candidate
            break

    if driver_col is None:
        raise ValueError("Session results missing a usable driver identity column.")

    points_map: dict[str, float] = {}
    for row in results_df.itertuples(index=False):
        driver = getattr(row, driver_col, None)
        if pd.isna(driver) or str(driver).strip() == "":
            continue

        raw_points = getattr(row, "Points", 0)
        points = pd.to_numeric(raw_points, errors="coerce")
        points_map[str(driver)] = float(0.0 if pd.isna(points) else points)

    return points_map


def main() -> None:
    """Create Chapter 1 website exports from supported race sessions."""
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input file not found at {INPUT_PATH}. Run src.pipeline.fetch_supported_sessions first."
        )

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    fastf1.Cache.enable_cache("f1_cache")

    sessions_df = pd.read_parquet(INPUT_PATH)
    race_rounds = _get_race_rounds(sessions_df)

    round_points: dict[int, dict[str, float]] = {}
    round_labels: list[dict[str, object]] = []

    for round_number, event_name in race_rounds:
        try:
            session = fastf1.get_session(TARGET_YEAR, round_number, "R")
            session.load(laps=False, telemetry=False, weather=False, messages=False)
            points_map = _extract_round_points(session.results)

            round_points[round_number] = points_map
            round_labels.append({"RoundNumber": round_number, "EventName": event_name})
        except Exception as exc:  # noqa: BLE001 - keep pipeline resilient per round
            print(f"Skipped round {round_number} ({event_name}): {exc}")

    processed_rounds = sorted(round_points.keys())
    driver_set = {driver for rnd in processed_rounds for driver in round_points[rnd].keys()}
    drivers = sorted(driver_set)

    heatmap_rows: list[dict[str, object]] = []
    progression_rows: list[dict[str, object]] = []

    for driver in drivers:
        heatmap_row: dict[str, object] = {"Driver": driver}
        progression_row: dict[str, object] = {"Driver": driver}
        cumulative_points = 0.0

        for rnd in processed_rounds:
            round_pts = float(round_points[rnd].get(driver, 0.0))
            cumulative_points += round_pts
            heatmap_row[str(rnd)] = round_pts
            progression_row[str(rnd)] = cumulative_points

        heatmap_rows.append(heatmap_row)
        progression_rows.append(progression_row)

    standings_payload = {
        "rounds": round_labels,
        "drivers": drivers,
        "rows": progression_rows,
    }
    heatmap_payload = {
        "rounds": round_labels,
        "drivers": drivers,
        "rows": heatmap_rows,
    }

    with open(STANDINGS_OUT, "w", encoding="utf-8") as f:
        json.dump(standings_payload, f, indent=2)

    with open(HEATMAP_OUT, "w", encoding="utf-8") as f:
        json.dump(heatmap_payload, f, indent=2)

    print(f"rounds processed: {len(processed_rounds)}")
    print(f"drivers count: {len(drivers)}")
    print(f"outputs: {STANDINGS_OUT}, {HEATMAP_OUT}")


if __name__ == "__main__":
    main()
