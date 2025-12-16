"""
Enums for property listing data models.
"""

from enum import Enum


class ListingStatus(str, Enum):
    """Status of a property listing."""

    SCHEDULED = "scheduled"  # Auction is scheduled
    CANCELLED = "cancelled"  # Auction was cancelled
    VOIDED = "voided"  # Auction was voided
    SOLD = "sold"  # Property has been sold
    WITHDRAWN = "withdrawn"  # Listing withdrawn from market
    ACTIVE = "active"  # Active listing (no auction scheduled)
    UNDER_OFFER = "under_offer"  # Property is under offer
    UNKNOWN = "unknown"  # Status unknown or not specified

    def __str__(self) -> str:
        return self.value


class PropertyType(str, Enum):
    """Type of property."""

    HOUSE = "house"
    UNIT = "unit"
    APARTMENT = "apartment"
    TOWNHOUSE = "townhouse"
    VILLA = "villa"
    LAND = "land"
    STUDIO = "studio"
    OTHER = "other"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_string(cls, value: str) -> "PropertyType":
        """Convert string to PropertyType, handling variations."""
        if not value:
            return cls.OTHER

        value_lower = value.lower().strip()

        # Handle common variations
        if "house" in value_lower:
            return cls.HOUSE
        elif "unit" in value_lower or "flat" in value_lower:
            return cls.UNIT
        elif "apartment" in value_lower:
            return cls.APARTMENT
        elif "townhouse" in value_lower or "town house" in value_lower:
            return cls.TOWNHOUSE
        elif "villa" in value_lower:
            return cls.VILLA
        elif "land" in value_lower:
            return cls.LAND
        elif "studio" in value_lower:
            return cls.STUDIO
        else:
            return cls.OTHER

