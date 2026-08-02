#!/usr/bin/env python3
"""
Continuous background runner.

Runs forever:
  1. Scrape realestate.com.au  → scaper/realestatecom-scraper/results/search.json
  2. Scrape domain.com.au      → scaper/domaincom-scraper/results/search.json
  3. Ingest realestate results → Supabase
  4. Ingest domain results     → Supabase
  5. Wait 30 minutes
  6. Repeat

Usage:
    python run.py

Env vars required (copy .env.example → .env and fill in):
    SUPABASE_URL
    SUPABASE_KEY
    SCRAPFLY_KEY      (for realestate.com.au)
    DOMAIN_API_KEY    (for domain.com.au)
"""

import subprocess
import sys
import time
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
REALESTATE_SCRAPER = ROOT / "scaper" / "realestatecom-scraper"
DOMAIN_SCRAPER = ROOT / "scaper" / "domaincom-scraper"
REALESTATE_RESULTS = REALESTATE_SCRAPER / "results" / "search.json"
DOMAIN_RESULTS = DOMAIN_SCRAPER / "results" / "search.json"
INGEST_SCRIPT = ROOT / "ingestion" / "ingest.py"

LOOP_INTERVAL_SECONDS = 30 * 60  # 30 minutes


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_step(label: str, cmd: list, cwd: Path, env: dict) -> bool:
    """Run a subprocess step. Returns True on success, False on failure."""
    log(f"START  {label}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=False,  # let output stream to console
            timeout=600,           # 10 min hard cap per step
        )
        if result.returncode == 0:
            log(f"OK     {label}")
            return True
        else:
            log(f"FAIL   {label} (exit code {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        log(f"FAIL   {label} (timed out after 10 min)")
        return False
    except Exception as e:
        log(f"FAIL   {label} ({e})")
        return False


def one_cycle() -> None:
    env = {**os.environ}  # pass through all env vars including SCRAPFLY_KEY etc.

    # ── 1. Scrape realestate.com.au ───────────────────────────────────────────
    run_step(
        "Scrape realestate.com.au",
        [sys.executable, "run.py"],
        cwd=REALESTATE_SCRAPER,
        env=env,
    )

    # ── 2. Scrape domain.com.au ───────────────────────────────────────────────
    run_step(
        "Scrape domain.com.au",
        [sys.executable, "run.py"],
        cwd=DOMAIN_SCRAPER,
        env=env,
    )

    # ── 3. Ingest realestate results ──────────────────────────────────────────
    if REALESTATE_RESULTS.exists():
        run_step(
            "Ingest realestate.com.au results",
            [sys.executable, str(INGEST_SCRIPT), str(REALESTATE_RESULTS), "--source", "realestate"],
            cwd=ROOT,
            env=env,
        )
    else:
        log(f"SKIP   Ingest realestate (no results file at {REALESTATE_RESULTS})")

    # ── 4. Ingest domain results ──────────────────────────────────────────────
    if DOMAIN_RESULTS.exists():
        run_step(
            "Ingest domain.com.au results",
            [sys.executable, str(INGEST_SCRIPT), str(DOMAIN_RESULTS), "--source", "domain"],
            cwd=ROOT,
            env=env,
        )
    else:
        log(f"SKIP   Ingest domain (no results file at {DOMAIN_RESULTS})")


def main() -> None:
    log("=== Background runner started ===")
    log(f"Cycle interval: {LOOP_INTERVAL_SECONDS // 60} minutes")

    cycle = 0
    while True:
        cycle += 1
        log(f"--- Cycle {cycle} begin ---")
        try:
            one_cycle()
        except Exception as e:
            log(f"ERROR  Unexpected error in cycle {cycle}: {e}")

        log(f"--- Cycle {cycle} complete — sleeping {LOOP_INTERVAL_SECONDS // 60}m ---")
        time.sleep(LOOP_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
