"""Generate Chapter 2 qualifying exports: q3 gaps and pole-to-win conversion."""

from __future__ import annotations

import json
from collections import defaultdict

import fastf1
import pandas as pd

from src.utils.config import EXPORTS_DIR

TARGET_YEAR = 2025
Q3_GAPS_OUT = EXPORTS_DIR / "q3_gaps.json"
POLE_TO_WIN_OUT = EXPORTS_DIR / "pole_to_win.json"


def _get_rounds_for_year(year: int) -> list[dict[str, object]]:
    """Return race weekends for a season sorted by round number."""
    schedule = fastf1.get_event_schedule(year)
    if not isinstance(schedule, pd.DataFrame):
        schedule = pd.DataFrame(schedule)

    required = ["RoundNumber", "EventName"]
    missing = [col for col in required if col not in schedule.columns]
    if missing:
        raise ValueError(f"Schedule missing required columns: {missing}")

    rounds_df = schedule.copy()
    rounds_df["RoundNumber"] = pd.to_numeric(rounds_df["RoundNumber"], errors="coerce")
    rounds_df = rounds_df.dropna(subset=["RoundNumber"])
    rounds_df["RoundNumber"] = rounds_df["RoundNumber"].astype(int)
    rounds_df = rounds_df[rounds_df["RoundNumber"] > 0]

    rounds_df = rounds_df.sort_values("RoundNumber").drop_duplicates(subset=["RoundNumber"], keep="first")
    return [
        {"round": int(row.RoundNumber), "event_name": str(row.EventName)}
        for row in rounds_df.itertuples(index=False)
    ]


def _extract_q3_records(results_df: pd.DataFrame, round_number: int, event_name: str) -> list[dict[str, object]]:
    """Build Q3 gap records for a round."""
    if results_df is None or results_df.empty:
        return []

    required = ["Abbreviation", "TeamName", "Q3"]
    missing = [col for col in required if col not in results_df.columns]
    if missing:
        raise ValueError(f"Qualifying results missing columns: {missing}")

    df = results_df.copy()
    df["Q3_td"] = pd.to_timedelta(df["Q3"], errors="coerce")
    q3_df = df.dropna(subset=["Q3_td"]).copy()
    if q3_df.empty:
        return []

    pole_td = q3_df["Q3_td"].min()
    pole_sec = round(float(pole_td.total_seconds()), 3)

    q3_df["q3_time_sec"] = q3_df["Q3_td"].dt.total_seconds()
    q3_df["gap_to_pole_sec"] = q3_df["q3_time_sec"] - float(pole_td.total_seconds())
    q3_df = q3_df.sort_values(["gap_to_pole_sec", "Abbreviation"], ascending=[True, True])

    records: list[dict[str, object]] = []
    for row in q3_df.itertuples(index=False):
        records.append(
            {
                "round": round_number,
                "event_name": event_name,
                "driver": str(row.Abbreviation),
                "team": str(row.TeamName),
                "q3_time": round(float(row.q3_time_sec), 3),
                "pole_time": pole_sec,
                "gap_to_pole_sec": round(float(row.gap_to_pole_sec), 3),
            }
        )

    return records


def _get_race_winner_abbr(results_df: pd.DataFrame) -> str | None:
    """Return winning driver abbreviation from race results, if available."""
    if results_df is None or results_df.empty:
        return None

    if "Position" not in results_df.columns or "Abbreviation" not in results_df.columns:
        return None

    df = results_df.copy()
    df["Position_num"] = pd.to_numeric(df["Position"], errors="coerce")
    winner = df[df["Position_num"] == 1]
    if winner.empty:
        return None

    value = winner.iloc[0]["Abbreviation"]
    if pd.isna(value) or str(value).strip() == "":
        return None
    return str(value)


def main() -> None:
    """Export q3 gaps and pole-to-win conversion for the 2025 season."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Required by task instructions.
    fastf1.Cache.enable_cache("f1_cache")

    rounds = _get_rounds_for_year(TARGET_YEAR)
    rounds_attempted = len(rounds)

    q3_records: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    conversion_rounds: list[dict[str, object]] = []

    for item in rounds:
        round_number = int(item["round"])
        event_name = str(item["event_name"])

        try:
            quali = fastf1.get_session(TARGET_YEAR, round_number, "Q")
            quali.load(laps=False, telemetry=False, weather=False, messages=False)
        except Exception as exc:  # noqa: BLE001 - pipeline should continue per round
            skipped.append(
                {"round": round_number, "event_name": event_name, "reason": f"qualifying_load_failed: {exc}"}
            )
            continue

        try:
            q3_round_records = _extract_q3_records(quali.results, round_number, event_name)
        except Exception as exc:  # noqa: BLE001 - schema or parsing issues should not kill run
            skipped.append(
                {"round": round_number, "event_name": event_name, "reason": f"qualifying_parse_failed: {exc}"}
            )
            continue

        if not q3_round_records:
            skipped.append(
                {"round": round_number, "event_name": event_name, "reason": "no_q3_times"}
            )
            continue

        q3_records.extend(q3_round_records)
        pole_sitter = q3_round_records[0]["driver"]

        try:
            race = fastf1.get_session(TARGET_YEAR, round_number, "R")
            race.load(laps=False, telemetry=False, weather=False, messages=False)
            race_winner = _get_race_winner_abbr(race.results)
        except Exception as exc:  # noqa: BLE001 - keep q3 export even if race conversion fails
            race_winner = None
            skipped.append(
                {
                    "round": round_number,
                    "event_name": event_name,
                    "reason": f"race_load_failed_for_conversion: {exc}",
                }
            )

        if race_winner is not None:
            conversion_rounds.append(
                {
                    "round": round_number,
                    "event_name": event_name,
                    "pole_sitter": pole_sitter,
                    "race_winner": race_winner,
                }
            )

    q3_records = sorted(q3_records, key=lambda x: (x["round"], x["gap_to_pole_sec"], x["driver"]))
    conversion_rounds = sorted(conversion_rounds, key=lambda x: x["round"])
    skipped = sorted(skipped, key=lambda x: (x["round"], x["reason"]))

    poles_by_driver: dict[str, int] = defaultdict(int)
    wins_from_pole_by_driver: dict[str, int] = defaultdict(int)
    for rnd in conversion_rounds:
        pole = rnd["pole_sitter"]
        winner = rnd["race_winner"]
        poles_by_driver[pole] += 1
        if pole == winner:
            wins_from_pole_by_driver[pole] += 1

    pole_to_win_rows: list[dict[str, object]] = []
    for driver in sorted(poles_by_driver.keys()):
        poles = poles_by_driver[driver]
        wins_from_pole = wins_from_pole_by_driver.get(driver, 0)
        conversion_rate = 0.0 if poles == 0 else round(wins_from_pole / poles, 3)
        pole_to_win_rows.append(
            {
                "driver": driver,
                "poles": poles,
                "wins_from_pole": wins_from_pole,
                "conversion_rate": conversion_rate,
            }
        )

    q3_payload = {
        "year": TARGET_YEAR,
        "records": q3_records,
    }
    pole_to_win_payload = {
        "year": TARGET_YEAR,
        "records": pole_to_win_rows,
        "rounds_used_for_conversion": conversion_rounds,
    }

    with open(Q3_GAPS_OUT, "w", encoding="utf-8") as f:
        json.dump(q3_payload, f, indent=2, sort_keys=True)

    with open(POLE_TO_WIN_OUT, "w", encoding="utf-8") as f:
        json.dump(pole_to_win_payload, f, indent=2, sort_keys=True)

    processed_rounds = sorted({record["round"] for record in q3_records})
    print(f"rounds attempted: {rounds_attempted}")
    print(f"rounds processed: {len(processed_rounds)}")
    print("skipped:")
    for item in skipped:
        print(f"- round {item['round']} ({item['event_name']}): {item['reason']}")
    print(f"output q3_gaps: {Q3_GAPS_OUT}")
    print(f"output pole_to_win: {POLE_TO_WIN_OUT}")


if __name__ == "__main__":
    main()
