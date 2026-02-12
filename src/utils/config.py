"""Project configuration for F1 Data Intelligence Report 2025."""

from pathlib import Path

# Central cache directory for FastF1
FASTF1_CACHE_DIR = Path("f1_cache")

# Report year(s)
years = 2025

# Output directories
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"