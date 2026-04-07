"""
Listing ingestion system for property listings.

This package provides functionality to ingest property listings from JSON files
into Supabase database with change detection and automatic event generation.
"""

from .database import SupabaseRepository
from .ingester import Ingester
from .pipeline import Pipeline
from .readers import JSONReader, RealestateReader, DomainReader
from .scheduler import Scheduler

__all__ = [
    "SupabaseRepository",
    "Ingester",
    "Pipeline",
    "Scheduler",
    "JSONReader",
    "RealestateReader",
    "DomainReader",
]

