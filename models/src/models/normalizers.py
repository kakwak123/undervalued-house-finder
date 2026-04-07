"""
Utilities for normalizing scraper data into Listing models.

This module provides functions to convert raw scraper JSON data
into standardized Listing models.
"""

import html
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, Any

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
                # Remove any non-numeric characters except decimal point
                # Handle cases like "554", "554.5", "554 m²", etc.
                cleaned_value = str(land_value).strip()
                match = re.search(r"[\d.]+", cleaned_value)
                if match:
                    land_size = Decimal(match.group())
            except (ValueError, TypeError, Exception):
                pass

    if property_sizes.get("building"):
        building_value = property_sizes["building"].get("displayValue")
        if building_value:
            try:
                # Remove any non-numeric characters except decimal point
                cleaned_value = str(building_value).strip()
                match = re.search(r"[\d.]+", cleaned_value)
                if match:
                    building_size = Decimal(match.group())
            except (ValueError, TypeError, Exception):
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

    # Extract price from description or propertyFeatures
    current_price = None
    description = data.get("description", "")
    
    # Try to extract price from description (common patterns)
    if description:
        # Remove HTML tags and decode entities
        clean_desc = re.sub(r"<[^>]+>", " ", description)
        clean_desc = html.unescape(clean_desc)
        
        # Look for price patterns like "$760,000", "$760,000 - $820,000", "PRICE GUIDE $760,000"
        # Match dollar amounts with commas: $760,000 or $760000
        price_pattern = r'\$[\d,]+(?:\.[\d]+)?'
        matches = re.findall(price_pattern, clean_desc)
        
        if matches:
            # Take the first price found (or lower value if range)
            price_str = matches[0].replace('$', '').replace(',', '')
            try:
                price_value = float(price_str)
                # Only accept reasonable property prices (between 10k and 100M)
                if 10000 <= price_value <= 100000000:
                    current_price = Decimal(str(int(price_value)))
            except (ValueError, TypeError):
                pass
    
    # Also check propertyFeatures for price information
    property_features = data.get("propertyFeatures", [])
    if property_features and current_price is None:
        for feature in property_features:
            feature_name = str(feature.get("featureName", "")).lower()
            if "price" in feature_name or "cost" in feature_name:
                value = feature.get("value")
                if value:
                    try:
                        # Try to extract numeric value
                        if isinstance(value, (int, float)):
                            current_price = Decimal(str(int(value)))
                        elif isinstance(value, str):
                            price_str = re.sub(r'[^\d.]', '', value)
                            if price_str:
                                current_price = Decimal(str(int(float(price_str))))
                    except (ValueError, TypeError):
                        continue
                if current_price:
                    break

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
        current_price=current_price,
        auction_datetime=auction_datetime,
        property_link=data.get("propertyLink"),
        description=description,
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

