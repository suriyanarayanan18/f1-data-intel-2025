# F1 Data Intelligence Report 2025

Repository scaffold for data collection, processing, and exports used by the F1 Data Intelligence web report.

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run Pipeline Scripts

From the repository root, run pipeline modules with Python. Example:

```bash
python -m src.pipeline.fetch_schedule
```

This will fetch the 2025 F1 schedule and write processed outputs.

## Export Location For Website

Website-ready export artifacts should be written to:

- `data/exports/`

The static site or frontend layer in `web/` can consume files from that folder.