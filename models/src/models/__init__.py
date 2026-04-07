"""
Core data models for property listings.

This module provides the data models for property listings, including
enums for status tracking and models for price/auction history.
"""

from .enums import ListingStatus, PropertyType, EventType, ValuationClassification
from .listing import Listing, PriceHistory, AuctionHistory
from .address import Address
from .events import Event, EventTimeline
from .normalizers import normalize_realestate_data, normalize_domain_data
from .valuation import PriceModel, ValuationResult, UndervaluationDetector, compute_undervalue_score
from .scoring import OpportunityScorer, OpportunityScore

__all__ = [
    "Listing",
    "ListingStatus",
    "PropertyType",
    "EventType",
    "ValuationClassification",
    "Address",
    "PriceHistory",
    "AuctionHistory",
    "Event",
    "EventTimeline",
    "normalize_realestate_data",
    "normalize_domain_data",
    "PriceModel",
    "ValuationResult",
    "UndervaluationDetector",
    "compute_undervalue_score",
    "OpportunityScorer",
    "OpportunityScore",
]

