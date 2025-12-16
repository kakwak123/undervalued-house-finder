"""
Address model for property listings.
"""

from typing import Optional
from pydantic import BaseModel, Field


class Address(BaseModel):
    """Address information for a property listing."""

    street_number: Optional[str] = Field(None, description="Street number")
    street_name: Optional[str] = Field(None, description="Street name")
    unit_number: Optional[str] = Field(None, description="Unit/apartment number")
    suburb: str = Field(..., description="Suburb name")
    state: str = Field(..., description="State abbreviation (e.g., 'Vic', 'NSW')")
    postcode: str = Field(..., description="Postal code")
    full_address: Optional[str] = Field(None, description="Full formatted address")
    short_address: Optional[str] = Field(None, description="Short address format")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "street_number": "31",
                "street_name": "Aberdeen Drive",
                "suburb": "Dandenong North",
                "state": "Vic",
                "postcode": "3175",
                "full_address": "31 Aberdeen Drive, Dandenong North, Vic 3175",
                "short_address": "31 Aberdeen Drive",
            }
        }

