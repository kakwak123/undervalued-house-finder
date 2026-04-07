"""
JSON file readers for different scraper formats.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Iterator

# Add models package to path
models_path = Path(__file__).parent.parent.parent.parent.parent / "models" / "src"
sys.path.insert(0, str(models_path))

from models import Listing, normalize_realestate_data, normalize_domain_data


class JSONReader:
    """Base class for reading JSON files."""

    def __init__(self, file_path: Path):
        """
        Initialize reader with file path.

        Args:
            file_path: Path to JSON file
        """
        self.file_path = Path(file_path)

    def read(self) -> List[Dict[str, Any]]:
        """
        Read and parse JSON file.

        Returns:
            List of JSON objects
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        with open(self.file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle both array and single object
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            return []


class RealestateReader(JSONReader):
    """
    Reader for realestate.com.au scraper JSON format.
    """

    def read_listings(self) -> Iterator[Listing]:
        """
        Read listings from realestate.com.au JSON format.

        Yields:
            Listing model instances
        """
        data = self.read()
        yield from self._normalise(data)

    @classmethod
    def from_data(cls, data: List[Dict[str, Any]]) -> Iterator[Listing]:
        """
        Normalise an in-memory list of raw realestate.com.au dicts.

        Used by the scrape-to-ingest pipeline (S-2) to bypass the JSON file step.

        Args:
            data: Raw property dicts returned by the realestate.com.au scraper.

        Yields:
            Listing model instances
        """
        yield from cls._normalise(data)

    @staticmethod
    def _normalise(data: List[Dict[str, Any]]) -> Iterator[Listing]:
        """Shared normalisation logic for both file-based and in-memory paths."""
        for item in data:
            try:
                listing = normalize_realestate_data(item)
                yield listing
            except Exception as e:
                print(f"Error normalizing listing {item.get('id', 'unknown')}: {e}")
                continue


class DomainReader(JSONReader):
    """
    Reader for domain.com.au scraper JSON format.
    """

    def read_listings(self) -> Iterator[Listing]:
        """
        Read listings from domain.com.au JSON format.

        Yields:
            Listing model instances
        """
        data = self.read()
        yield from self._normalise(data)

    @classmethod
    def from_data(cls, data: List[Dict[str, Any]]) -> Iterator[Listing]:
        """
        Normalise an in-memory list of raw domain.com.au dicts.

        Used by the scrape-to-ingest pipeline (S-2) to bypass the JSON file step.

        Args:
            data: Raw property dicts returned by the domain.com.au scraper.

        Yields:
            Listing model instances
        """
        yield from cls._normalise(data)

    @staticmethod
    def _normalise(data: List[Dict[str, Any]]) -> Iterator[Listing]:
        """Shared normalisation logic for both file-based and in-memory paths."""
        for item in data:
            try:
                listing = normalize_domain_data(item)
                yield listing
            except Exception as e:
                print(f"Error normalizing listing {item.get('listingId', 'unknown')}: {e}")
                continue


def detect_reader_type(file_path: Path) -> str:
    """
    Detect the scraper type from file path or content.

    Args:
        file_path: Path to JSON file

    Returns:
        Reader type: 'realestate', 'domain', or 'auto'
    """
    # Check file path for hints
    path_str = str(file_path).lower()
    if "realestate" in path_str or "realestatecom" in path_str:
        return "realestate"
    elif "domain" in path_str or "domaincom" in path_str:
        return "domain"

    # Try to detect from content
    try:
        reader = JSONReader(file_path)
        data = reader.read()
        if data:
            first_item = data[0] if isinstance(data, list) else data

            # Check for realestate.com.au indicators
            if "id" in first_item and "propertyLink" in first_item:
                if "realestate.com.au" in str(first_item.get("propertyLink", "")):
                    return "realestate"

            # Check for domain.com.au indicators
            if "listingId" in first_item or "listingUrl" in first_item:
                if "domain.com.au" in str(first_item.get("listingUrl", "")):
                    return "domain"
    except Exception:
        pass

    return "auto"

