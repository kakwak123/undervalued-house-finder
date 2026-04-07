"""
Example script to ingest test data.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
ingestion_src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(ingestion_src))

# Add models package path
models_path = Path(__file__).parent.parent.parent / "models" / "src"
if models_path.exists():
    sys.path.insert(0, str(models_path))

from ingestion import SupabaseRepository, Ingester

# Supabase configuration — set via env vars or .env file
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def main():
    """Ingest test data from testdata/search.json."""
    # Get project root (3 levels up from examples/)
    project_root = Path(__file__).parent.parent.parent
    testdata_file = project_root / "testdata" / "search.json"

    if not testdata_file.exists():
        print(f"Error: Test data file not found: {testdata_file}")
        sys.exit(1)

    print("Initializing Supabase repository...")
    repository = SupabaseRepository(SUPABASE_URL, SUPABASE_KEY)

    print("Creating ingester...")
    ingester = Ingester(repository)

    print(f"Ingesting listings from: {testdata_file}")
    print("Source: realestate.com.au (auto-detected)")

    try:
        ingester.ingest_file(testdata_file, source_type="realestate")

        # Print statistics
        stats = ingester.get_stats()
        print("\n" + "=" * 50)
        print("Ingestion Complete!")
        print("=" * 50)
        print(f"Processed:     {stats['processed']}")
        print(f"Created:       {stats['created']}")
        print(f"Updated:       {stats['updated']}")
        print(f"Events:        {stats['events_generated']}")
        print(f"Errors:        {stats['errors']}")
        print("=" * 50)
    except Exception as e:
        print(f"Error during ingestion: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

