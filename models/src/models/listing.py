"""
Core listing data model with price and auction history support.
"""

from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator

from .enums import ListingStatus, PropertyType
from .address import Address


class PriceHistory(BaseModel):
    """Historical price record for a listing."""

    price: Decimal = Field(..., description="Price at this point in time")
    timestamp: datetime = Field(..., description="When this price was recorded")
    source: Optional[str] = Field(None, description="Source of the price data")

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }


class AuctionHistory(BaseModel):
    """Historical auction record for a listing."""

    auction_datetime: datetime = Field(..., description="Scheduled auction date and time")
    status: ListingStatus = Field(..., description="Status of this auction")
    timestamp: datetime = Field(..., description="When this auction record was created")
    notes: Optional[str] = Field(None, description="Additional notes about the auction")

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class Listing(BaseModel):
    """
    Core property listing data model.

    Supports price and auction history tracking as required by the acceptance criteria.
    """

    # Required core fields
    listing_id: str = Field(..., description="Unique listing identifier")
    address: Address = Field(..., description="Property address")
    suburb: str = Field(..., description="Suburb name (also in address, kept for convenience)")
    property_type: PropertyType = Field(..., description="Type of property")

    # Property features
    bedrooms: Optional[int] = Field(None, ge=0, description="Number of bedrooms")
    bathrooms: Optional[int] = Field(None, ge=0, description="Number of bathrooms")
    land_size: Optional[Decimal] = Field(None, ge=0, description="Land size in square meters")
    building_size: Optional[Decimal] = Field(None, ge=0, description="Building size in square meters")

    # Status and pricing
    status: ListingStatus = Field(
        default=ListingStatus.UNKNOWN,
        description="Current listing status (enum-based as required)",
    )
    current_price: Optional[Decimal] = Field(None, ge=0, description="Current listing price")
    previous_price: Optional[Decimal] = Field(None, ge=0, description="Previous listing price")

    # Auction information
    auction_datetime: Optional[datetime] = Field(
        None, description="Next scheduled auction date and time"
    )

    # History tracking (required by acceptance criteria)
    price_history: List[PriceHistory] = Field(
        default_factory=list,
        description="Historical price records",
    )
    auction_history: List[AuctionHistory] = Field(
        default_factory=list,
        description="Historical auction records",
    )

    # Additional metadata
    property_link: Optional[str] = Field(None, description="URL to property listing")
    description: Optional[str] = Field(None, description="Property description")
    created_at: Optional[datetime] = Field(None, description="When listing was first created")
    updated_at: Optional[datetime] = Field(None, description="When listing was last updated")
    source: Optional[str] = Field(None, description="Data source (e.g., 'realestate.com.au')")

    @field_validator("suburb")
    @classmethod
    def validate_suburb(cls, v: str) -> str:
        """Ensure suburb matches address suburb."""
        return v.strip()

    def add_price_record(self, price: Decimal, timestamp: Optional[datetime] = None) -> None:
        """
        Add a price record to history and update current/previous prices.

        Args:
            price: The new price
            timestamp: When this price was recorded (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Update previous price if current price exists
        if self.current_price is not None:
            self.previous_price = self.current_price

        # Update current price
        self.current_price = price

        # Add to history
        self.price_history.append(
            PriceHistory(price=price, timestamp=timestamp)
        )

        # Sort history by timestamp (most recent first)
        self.price_history.sort(key=lambda x: x.timestamp, reverse=True)

    def add_auction_record(
        self,
        auction_datetime: datetime,
        status: ListingStatus,
        timestamp: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> None:
        """
        Add an auction record to history.

        Args:
            auction_datetime: Scheduled auction date and time
            status: Status of the auction
            timestamp: When this record was created (defaults to now)
            notes: Additional notes
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Update current auction datetime if this is the most recent scheduled auction
        if status == ListingStatus.SCHEDULED:
            if self.auction_datetime is None or auction_datetime > self.auction_datetime:
                self.auction_datetime = auction_datetime

        # Update status
        self.status = status

        # Add to history
        self.auction_history.append(
            AuctionHistory(
                auction_datetime=auction_datetime,
                status=status,
                timestamp=timestamp,
                notes=notes,
            )
        )

        # Sort history by timestamp (most recent first)
        self.auction_history.sort(key=lambda x: x.timestamp, reverse=True)

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
        json_schema_extra = {
            "example": {
                "listing_id": "149785064",
                "address": {
                    "street_number": "31",
                    "street_name": "Aberdeen Drive",
                    "suburb": "Dandenong North",
                    "state": "Vic",
                    "postcode": "3175",
                    "full_address": "31 Aberdeen Drive, Dandenong North, Vic 3175",
                },
                "suburb": "Dandenong North",
                "property_type": "house",
                "bedrooms": 6,
                "bathrooms": 2,
                "land_size": "554",
                "status": "scheduled",
                "current_price": "750000",
                "previous_price": "800000",
                "auction_datetime": "2024-12-20T10:00:00Z",
                "price_history": [],
                "auction_history": [],
            }
        }

