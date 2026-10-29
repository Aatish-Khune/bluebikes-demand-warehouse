"""Cross-platform task runner (works on Windows without `make`).

    python run.py data      # download 12 months of trips + weather, load raw.* into DuckDB
    python run.py dbt       # dbt build: staging -> marts -> analytics, with all data tests
    python run.py forecast  # seasonal-naive vs. LightGBM station demand forecast -> reports/
    python run.py export    # write small aggregated tables for the app -> artifacts/
    python run.py test      # lint + unit tests
    python run.py app       # launch the Streamlit dashboard
    python run.py all       # data + dbt + forecast + export
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def dbt(*args: str) -> int:
    """Run dbt in-process with config and outputs kept inside the project."""
    from bluebikes.config import DBT_DIR, dbt_env

    os.environ.update(dbt_env())
    from dbt.cli.main import dbtRunner

    result = dbtRunner().invoke(
        [*args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    )
    return 0 if result.success else 1


def main(cmd: str) -> int:
    steps = {"data", "dbt", "forecast", "export", "all"}
    if cmd in ("data", "all"):
        from bluebikes.ingest import main as ingest

        ingest()
    if cmd in ("dbt", "all") and dbt("build"):  # build = seeds + models + tests, in DAG order
        return 1
    if cmd in ("forecast", "all"):
        from bluebikes.forecast import run_forecast

        run_forecast()
    if cmd in ("export", "all"):
        from bluebikes.export import export_artifacts

        export_artifacts()
    if cmd == "test":
        lint = subprocess.call([sys.executable, "-m", "ruff", "check", "."], cwd=ROOT)
        return lint or subprocess.call([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
    if cmd == "app":
        return subprocess.call(
            [sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py")],
            cwd=ROOT,
        )
    if cmd not in steps:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
