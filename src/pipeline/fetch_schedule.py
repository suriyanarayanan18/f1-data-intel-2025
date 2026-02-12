"""Fetch and persist the 2025 Formula 1 event schedule."""

import fastf1
import pandas as pd

from src.utils.config import FASTF1_CACHE_DIR, PROCESSED_DIR


def main() -> None:
    """Fetch 2025 schedule and save parquet + JSON outputs."""
    FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    fastf1.Cache.enable_cache(str(FASTF1_CACHE_DIR))

    schedule = fastf1.get_event_schedule(2025)
    if isinstance(schedule, pd.DataFrame):
        schedule_df = schedule.copy()
    else:
        schedule_df = pd.DataFrame(schedule)

    parquet_path = PROCESSED_DIR / "schedule_2025.parquet"
    json_path = PROCESSED_DIR / "schedule_2025.json"

    schedule_df.to_parquet(parquet_path, index=False)
    schedule_df.to_json(json_path, orient="records", indent=2, date_format="iso")

    if "EventName" in schedule_df.columns:
        event_names = schedule_df["EventName"].dropna().astype(str).tolist()
    else:
        # Fallback if schema changes
        event_names = []

    print(f"Fetched {len(schedule_df)} events for 2025.")
    if event_names:
        print("Events:")
        for name in event_names:
            print(f"- {name}")


if __name__ == "__main__":
    main()