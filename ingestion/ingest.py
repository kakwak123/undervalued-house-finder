#!/usr/bin/env python3
"""
Command-line interface for ingestion.
Entry point script that can be run directly.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Also add models package path
models_path = Path(__file__).parent.parent / "models" / "src"
if models_path.exists():
    sys.path.insert(0, str(models_path))

from dotenv import load_dotenv

from ingestion.database import SupabaseRepository
from ingestion.ingester import Ingester

# Load environment variables
load_dotenv()


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest property listings from JSON files")
    parser.add_argument(
        "file",
        type=str,
        help="Path to JSON file to ingest",
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["realestate", "domain", "auto"],
        default="auto",
        help="Source type (realestate, domain, or auto-detect)",
    )
    parser.add_argument(
        "--supabase-url",
        type=str,
        default=None,
        help="Supabase project URL (or set SUPABASE_URL env var)",
    )
    parser.add_argument(
        "--supabase-key",
        type=str,
        default=None,
        help="Supabase API key (or set SUPABASE_KEY env var)",
    )

    args = parser.parse_args()

    # Get Supabase credentials
    supabase_url = args.supabase_url or os.getenv("SUPABASE_URL")
    supabase_key = args.supabase_key or os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("Error: Supabase credentials required. Set SUPABASE_URL and SUPABASE_KEY env vars or use --supabase-url/--supabase-key flags.")
        print("Copy ingestion/.env.example to ingestion/.env and fill in your credentials.")
        sys.exit(1)

    # Initialize repository and ingester
    repository = SupabaseRepository(supabase_url, supabase_key)
    ingester = Ingester(repository)

    # Ingest file
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"Ingesting listings from: {file_path}")
    print(f"Source type: {args.source}")

    try:
        ingester.ingest_file(file_path, source_type=args.source if args.source != "auto" else None)

        # Print statistics
        stats = ingester.get_stats()
        print("\n=== Ingestion Complete ===")
        print(f"Processed: {stats['processed']}")
        print(f"Created: {stats['created']}")
        print(f"Updated: {stats['updated']}")
        print(f"Events Generated: {stats['events_generated']}")
        print(f"Errors: {stats['errors']}")
    except Exception as e:
        print(f"Error during ingestion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

