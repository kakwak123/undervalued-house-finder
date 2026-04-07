"""
Setup script to create database tables in Supabase.

This script uses the Supabase REST API to execute SQL and create the required tables.
"""

import os
import sys
from pathlib import Path

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase package not installed.")
    print("Install with: pip3 install -r requirements.txt")
    print("Or with Poetry: poetry install")
    sys.exit(1)

DEFAULT_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
DEFAULT_SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def read_schema_sql() -> str:
    """Read the SQL schema file."""
    schema_file = Path(__file__).parent / "supabase_schema.sql"
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    return schema_file.read_text()


def setup_database(supabase_url: str, supabase_key: str) -> bool:
    """
    Set up database tables in Supabase.

    Note: This requires the service_role key or RPC function to execute SQL.
    For production, you should run the SQL directly in Supabase SQL editor.

    Args:
        supabase_url: Supabase project URL
        supabase_key: Supabase API key

    Returns:
        True if successful, False otherwise
    """
    print("Connecting to Supabase...")
    client: Client = create_client(supabase_url, supabase_key)

    # Read SQL schema
    print("Reading schema file...")
    sql = read_schema_sql()

    # Note: The Supabase Python client doesn't have a direct SQL execution method
    # for security reasons. You need to either:
    # 1. Use the Supabase dashboard SQL editor (recommended)
    # 2. Use the REST API with service_role key
    # 3. Create a database function that can be called via RPC

    print("\n" + "=" * 60)
    print("IMPORTANT: Supabase Python client cannot execute raw SQL directly.")
    print("Please use one of these methods:")
    print("=" * 60)
    print("\n1. Supabase Dashboard (Recommended):")
    print("   - Go to https://supabase.com/dashboard")
    print("   - Select your project")
    print("   - Go to SQL Editor")
    print("   - Copy and paste the contents of supabase_schema.sql")
    print("   - Click 'Run'")
    print("\n2. Or use the Supabase CLI:")
    print("   - Install: npm install -g supabase")
    print("   - Run: supabase db push")
    print("\n3. Or manually verify tables exist:")
    print("   - Check if 'listings' and 'events' tables exist")
    print("=" * 60)

    # Try to verify tables exist by attempting a query
    print("\nVerifying tables...")
    try:
        # Try to query listings table
        result = client.table("listings").select("listing_id").limit(1).execute()
        print("✅ 'listings' table exists")
    except Exception as e:
        print(f"❌ 'listings' table not found or not accessible: {e}")
        print("   Please create the tables using the SQL schema file.")

    try:
        # Try to query events table
        result = client.table("events").select("id").limit(1).execute()
        print("✅ 'events' table exists")
    except Exception as e:
        print(f"❌ 'events' table not found or not accessible: {e}")
        print("   Please create the tables using the SQL schema file.")

    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Set up Supabase database tables")
    parser.add_argument(
        "--supabase-url",
        type=str,
        default=os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL),
        help="Supabase project URL",
    )
    parser.add_argument(
        "--supabase-key",
        type=str,
        default=os.getenv("SUPABASE_KEY", DEFAULT_SUPABASE_KEY),
        help="Supabase API key",
    )

    args = parser.parse_args()

    try:
        setup_database(args.supabase_url, args.supabase_key)
        print("\n✅ Setup check complete!")
        print("\nIf tables don't exist, please run the SQL schema manually in Supabase dashboard.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

