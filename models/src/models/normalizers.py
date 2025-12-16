"""
Utilities for normalizing scraper data into Listing models.

This module provides functions to convert raw scraper JSON data
into standardized Listing models.
"""

from typing import Dict, Optional, Any
from datetime import datetime
from decimal import Decimal

from .listing import Listing
from .address import Address
from .enums import ListingStatus, PropertyType


def normalize_realestate_data(data: Dict[str, Any]) -> Listing:
    """
    Normalize realestate.com.au scraper data into a Listing model.

    Args:
        data: Raw JSON data from realestate.com.au scraper

    Returns:
        Listing model instance
    """
    # Extract address
    address_data = data.get("address", {})
    display = address_data.get("display", {})
    
    address = Address(
        suburb=address_data.get("suburb", ""),
        state=address_data.get("state", ""),
        postcode=address_data.get("postcode", ""),
        full_address=display.get("fullAddress"),
        short_address=display.get("shortAddress"),
    )

    # Extract property sizes
    property_sizes = data.get("propertySizes", {})
    land_size = None
    building_size = None
    
    if property_sizes.get("land"):
        land_value = property_sizes["land"].get("displayValue")
        if land_value:
            try:
                land_size = Decimal(str(land_value))
            except (ValueError, TypeError):
                pass
    
    if property_sizes.get("building"):
        building_value = property_sizes["building"].get("displayValue")
        if building_value:
            try:
                building_size = Decimal(str(building_value))
            except (ValueError, TypeError):
                pass

    # Extract general features
    general_features = data.get("generalFeatures", {})
    bedrooms = general_features.get("bedrooms", {}).get("value")
    bathrooms = general_features.get("bathrooms", {}).get("value")

    # Extract property type
    property_type_str = data.get("propertyType", "")
    property_type = PropertyType.from_string(property_type_str)

    # Extract auction information
    auction_data = data.get("auction")
    auction_datetime = None
    status = ListingStatus.UNKNOWN
    
    if auction_data:
        # Parse auction datetime if available
        # Note: Actual format may vary, adjust as needed
        status = ListingStatus.SCHEDULED
        # auction_datetime would need to be parsed from auction_data

    # Create listing
    listing = Listing(
        listing_id=str(data.get("id", "")),
        address=address,
        suburb=address_data.get("suburb", ""),
        property_type=property_type,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        land_size=land_size,
        building_size=building_size,
        status=status,
        auction_datetime=auction_datetime,
        property_link=data.get("propertyLink"),
        description=data.get("description"),
        source="realestate.com.au",
    )

    return listing


def normalize_domain_data(data: Dict[str, Any]) -> Listing:
    """
    Normalize domain.com.au scraper data into a Listing model.

    Args:
        data: Raw JSON data from domain.com.au scraper

    Returns:
        Listing model instance
    """
    # Extract address
    address = Address(
        street_number=data.get("streetNumber"),
        street_name=data.get("street"),
        unit_number=data.get("unitNumber"),
        suburb=data.get("suburb", ""),
        state=data.get("state", ""),
        postcode=data.get("postcode", ""),
    )

    # Extract property type
    property_type_str = data.get("propertyType", "")
    property_type = PropertyType.from_string(property_type_str)

    # Extract property sizes (domain format may differ)
    land_size = None
    # Add parsing logic for domain.com.au land size format

    # Create listing
    listing = Listing(
        listing_id=str(data.get("listingId", "")),
        address=address,
        suburb=data.get("suburb", ""),
        property_type=property_type,
        bedrooms=data.get("beds"),
        bathrooms=data.get("baths"),  # May need to extract from listingSummary
        land_size=land_size,
        property_link=data.get("listingUrl"),
        description=" ".join(data.get("description", [])) if isinstance(data.get("description"), list) else data.get("description"),
        source="domain.com.au",
    )

    return listing

