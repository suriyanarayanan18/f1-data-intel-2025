"""Expand 2025 event schedule into supported sessions."""

from __future__ import annotations

import pandas as pd

from src.utils.config import PROCESSED_DIR


def _is_truthy(value: object) -> bool:
    """Return a permissive truthy interpretation for mixed-type values."""
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(value)


def _find_session_slots(columns: list[str]) -> list[int]:
    """Infer session slots from schedule columns like Session1..Session5."""
    slots: list[int] = []
    for col in columns:
        if col.startswith("Session") and col[7:].isdigit():
            slots.append(int(col[7:]))
    return sorted(set(slots))


def _expand_sessions(schedule_df: pd.DataFrame) -> pd.DataFrame:
    """Build one row per event session from a FastF1 schedule dataframe."""
    required_base = ["RoundNumber", "EventName", "EventDate"]
    missing_base = [c for c in required_base if c not in schedule_df.columns]
    if missing_base:
        raise ValueError(f"Missing required schedule columns: {missing_base}")

    session_slots = _find_session_slots(schedule_df.columns.tolist())
    if not session_slots:
        raise ValueError("No session columns found (expected Session1..SessionN).")

    has_support_col = "F1ApiSupport" in schedule_df.columns

    records: list[dict[str, object]] = []
    for _, row in schedule_df.iterrows():
        for slot in session_slots:
            session_name_col = f"Session{slot}"
            session_date_col = f"Session{slot}Date"

            if session_name_col not in schedule_df.columns:
                continue

            session_name = row.get(session_name_col)
            if pd.isna(session_name) or str(session_name).strip() == "":
                continue

            records.append(
                {
                    "RoundNumber": row.get("RoundNumber"),
                    "EventName": row.get("EventName"),
                    "EventDate": row.get("EventDate"),
                    "SessionName": session_name,
                    "SessionDate": row.get(session_date_col) if session_date_col in schedule_df.columns else pd.NaT,
                    "F1ApiSupport": row.get("F1ApiSupport") if has_support_col else True,
                }
            )

    sessions_df = pd.DataFrame(records)
    if sessions_df.empty:
        return sessions_df

    sessions_df["EventDate"] = pd.to_datetime(sessions_df["EventDate"], errors="coerce")
    sessions_df["SessionDate"] = pd.to_datetime(sessions_df["SessionDate"], errors="coerce")
    return sessions_df


def main() -> None:
    """Load schedule, derive supported sessions, and persist outputs."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    schedule_path = PROCESSED_DIR / "schedule_2025.parquet"
    if not schedule_path.exists():
        raise FileNotFoundError(
            f"Schedule file not found at {schedule_path}. Run src.pipeline.fetch_schedule first."
        )

    schedule_df = pd.read_parquet(schedule_path)
    sessions_df = _expand_sessions(schedule_df)

    total_sessions = len(sessions_df)

    support_column_present = "F1ApiSupport" in schedule_df.columns
    if not support_column_present:
        print("Warning: F1ApiSupport column not found in schedule. Assuming True for all sessions.")

    if total_sessions > 0:
        supported_mask = sessions_df["F1ApiSupport"].map(_is_truthy)
        supported_df = sessions_df.loc[supported_mask].copy()
    else:
        supported_df = sessions_df.copy()

    supported_parquet = PROCESSED_DIR / "supported_sessions_2025.parquet"
    supported_json = PROCESSED_DIR / "supported_sessions_2025.json"

    supported_df.to_parquet(supported_parquet, index=False)
    supported_df.to_json(supported_json, orient="records", indent=2, date_format="iso")

    print(f"total sessions: {total_sessions}")
    print(f"supported sessions: {len(supported_df)}")

    preview_cols = ["RoundNumber", "EventName", "SessionName", "SessionDate"]
    preview_df = supported_df.loc[:, preview_cols].head(15)

    for _, row in preview_df.iterrows():
        session_date = row["SessionDate"]
        if pd.isna(session_date):
            session_date_str = "NaT"
        else:
            session_date_str = pd.Timestamp(session_date).isoformat()
        print(
            f"{row['RoundNumber']} | {row['EventName']} | {row['SessionName']} | {session_date_str}"
        )


if __name__ == "__main__":
    main()
