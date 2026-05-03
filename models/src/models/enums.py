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

        # Handle common variations.  Order matters: check more specific
        # types before the substring "house" (so "Townhouse" isn't HOUSE),
        # and prefer UNIT for the realestate.com.au combined category
        # "Apartment / Unit / Flat" which contains both "apartment" and "unit".
        if "townhouse" in value_lower or "town house" in value_lower:
            return cls.TOWNHOUSE
        elif "unit" in value_lower or "flat" in value_lower:
            return cls.UNIT
        elif "apartment" in value_lower:
            return cls.APARTMENT
        elif "villa" in value_lower:
            return cls.VILLA
        elif "studio" in value_lower:
            return cls.STUDIO
        elif "land" in value_lower:
            return cls.LAND
        elif "house" in value_lower:
            return cls.HOUSE
        else:
            return cls.OTHER


class EventType(str, Enum):
    """Type of event that can occur for a listing."""

    AUCTION_CANCELLED = "auction_cancelled"
    AUCTION_RESCHEDULED = "auction_rescheduled"
    AUCTION_VOIDED = "auction_voided"
    PRICE_DROPPED = "price_dropped"
    UNDERVALUED_THRESHOLD_CROSSED = "undervalued_threshold_crossed"
    DISTRESS_SIGNAL = "distress_signal"

    def __str__(self) -> str:
        return self.value


class ValuationClassification(str, Enum):
    """Classification of a listing's valuation relative to estimated price."""

    SIGNIFICANTLY_UNDERVALUED = "significantly_undervalued"  # > 20 % below estimated
    UNDERVALUED = "undervalued"  # 10–20 % below estimated
    FAIR_VALUE = "fair_value"  # within ±10 % of estimated
    OVERPRICED = "overpriced"  # > 10 % above estimated

    def __str__(self) -> str:
        return self.value

