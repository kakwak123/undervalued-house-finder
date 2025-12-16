# Extracted Fields Documentation

This document outlines all the data fields extracted by the scrapers in this project.

## Domain.com.au Scraper

### Property Page Data (`scrape_properties`)

The Domain.com.au scraper extracts the following fields from individual property listing pages:

#### Basic Property Information
- **listingId** (integer): Unique listing identifier
- **listingUrl** (string): Full URL to the property listing
- **unitNumber** (string): Unit/apartment number (if applicable)
- **streetNumber** (string): Street number
- **street** (string): Street name
- **suburb** (string): Suburb name
- **postcode** (string): Postal code
- **createdOn** (datetime): Listing creation date
- **propertyType** (string): Type of property (e.g., "Apartment / Unit / Flat", "House")
- **beds** (integer): Number of bedrooms

#### Contact & Agency Information
- **phone** (string): Contact phone number
- **agencyName** (string): Real estate agency name
- **propertyDeveloperName** (string): Developer name (if applicable)
- **agencyProfileUrl** (string): URL to agency profile page
- **propertyDeveloperUrl** (string): URL to developer profile page

#### Property Details
- **description** (array of strings): Property description text (split into paragraphs)
- **loanfinder** (object/null): Loan finder information
- **features** (array): Property features list
- **structuredFeatures** (array): Structured property features

#### Media
- **gallery** (object): Image gallery with:
  - **slides** (array): Array of image objects containing:
    - **thumbnail**: Thumbnail image URL
    - **images**: Object with original, tablet, and mobile image URLs and dimensions
    - **embedUrl**: Video embed URL (if applicable)
    - **mediaType**: Type of media (e.g., "image")

#### Location & Schools
- **schools** (array): Nearby schools information, each containing:
  - **id**: School identifier
  - **educationLevel**: Level (primary, secondary, combined)
  - **name**: School name
  - **distance**: Distance in meters
  - **state**: State code
  - **postCode**: Postal code
  - **year**: Year levels
  - **gender**: Gender type
  - **type**: School type (Private, Government)
  - **address**: School address
  - **url**: School website URL
  - **domainSeoUrlSlug**: SEO URL slug
  - **status**: School status (e.g., "Open")

#### Suburb Insights
- **suburbInsights** (object): Comprehensive suburb data including:
  - **beds**: Number of bedrooms
  - **propertyType**: Property type
  - **suburb**: Suburb name
  - **suburbProfileUrl**: URL to suburb profile
  - **medianPrice**: Median property price
  - **medianRentPrice**: Median weekly rent
  - **avgDaysOnMarket**: Average days on market
  - **auctionClearance**: Auction clearance rate percentage
  - **nrSoldThisYear**: Number of properties sold this year
  - **entryLevelPrice**: Entry-level price
  - **luxuryLevelPrice**: Luxury-level price
  - **renterPercentage**: Percentage of renters
  - **singlePercentage**: Percentage of single occupants
  - **demographics**: Demographics data (population, avgAge, owners, renters, families, singles)
  - **salesGrowthList**: Historical sales data by year with:
    - **medianSoldPrice**: Median sold price for the year
    - **annualGrowth**: Annual growth percentage
    - **numberSold**: Number of properties sold
    - **year**: Year
    - **daysOnMarket**: Average days on market
  - **mostRecentSale**: Most recent sale information

#### Listing Summary
- **listingSummary** (object): Quick summary including:
  - **address**: Full address string
  - **baths**: Number of bathrooms
  - **beds**: Number of bedrooms
  - **houses**: Number of houses (if applicable)
  - **isRural**: Boolean indicating if rural property
  - **listingType**: Type of listing (e.g., "rent", "sale")
  - **mode**: Listing mode
  - **parking**: Number of parking spaces
  - **promoType**: Promotion type (e.g., "platinum")
  - **propertyType**: Property type
  - **showDefaultFeatures**: Boolean flag
  - **showDomainInsight**: Boolean flag
  - **stats**: Array of statistics (e.g., availableFrom date, bond amount)
  - **status**: Listing status (e.g., "new")
  - **title**: Price/title string (e.g., "$750 per week")

#### Agents
- **agents** (array): Array of agent objects, each containing:
  - **name**: Agent name
  - **photo**: Agent photo URL
  - **phone**: Phone number
  - **mobile**: Mobile number
  - **agentProfileUrl**: URL to agent profile
  - **email**: Base64 encoded email address

#### FAQs
- **faqs** (array): Frequently asked questions and answers about the property

#### Additional
- **url** (string): Property URL (added during scraping)

### Search Page Data (`scrape_search`)

From search result pages, the scraper extracts:
- **id**: Listing ID
- **listingType**: Type of listing
- **listingModel**: Full listing model data (excluding skeletonImages)

---

## Realestate.com.au Scraper

### Property Page Data (`scrape_properties`)

The Realestate.com.au scraper extracts the following fields from individual property listing pages:

#### Basic Property Information
- **id** (string): Unique property identifier
- **propertyType** (string): Type of property (e.g., "House", "Unit", "Apartment")
- **description** (string): HTML-formatted property description
- **propertyLink** (string): Canonical URL to the property listing

#### Address Information
- **address** (object): Complete address data including:
  - **suburb**: Suburb name
  - **state**: State abbreviation
  - **postcode**: Postal code
  - **display**: Display object with:
    - **shortAddress**: Short address format
    - **fullAddress**: Full address string
    - **geocode**: Geographic coordinates:
      - **latitude**: Latitude coordinate
      - **longitude**: Longitude coordinate

#### Property Sizes
- **propertySizes** (object): Size information including:
  - **building**: Building size (if applicable)
  - **land**: Land size with:
    - **displayValue**: Size value
    - **sizeUnit**: Unit of measurement (e.g., "m²")
  - **preferred**: Preferred size type (LAND or BUILDING) with size details

#### General Features
- **generalFeatures** (object): Basic property features:
  - **bedrooms**: Number of bedrooms (integer)
  - **bathrooms**: Number of bathrooms (integer)
  - **parkingSpaces**: Number of parking spaces (integer)
  - **studies**: Number of studies (integer)

#### Detailed Property Features
- **propertyFeatures** (array): Array of feature objects, each containing:
  - **featureName**: Name of the feature (e.g., "Built-in wardrobes", "Dishwasher", "Land size")
  - **value**: Feature value (can be null, numeric, or measurement object)

#### Media
- **images** (array): Array of image URLs (templated URLs with {size} placeholder)
- **videos** (array/null): Video URLs or null
- **floorplans** (array/null): Floor plan URLs or null

#### Listing Company (Agency)
- **listingCompany** (object): Real estate agency information:
  - **name**: Company name
  - **id**: Company identifier
  - **companyLink**: URL to company profile
  - **phoneNumber**: Business phone number
  - **address**: Full address string
  - **ratingsReviews**: Ratings and reviews data:
    - **avgRating**: Average rating (can be null)
    - **totalReviews**: Total number of reviews
  - **description**: Company description (can be null)

#### Agents (Listers)
- **listers** (array): Array of agent/lister objects, each containing:
  - **id**: Lister identifier
  - **name**: Agent name
  - **photo**: Photo object with templated URL
  - **phoneNumber**: Phone number object with display value
  - **_links**: Links object with canonical URL to agent profile
  - **agentId**: Agent ID (can be null)
  - **jobTitle**: Job title (e.g., "OIEC/Director", "Sales Director")
  - **showInMediaViewer**: Boolean flag
  - **listerRatingsReviews**: Ratings and reviews for the lister

#### Auction Information
- **auction** (object/null): Auction details if applicable, or null

### Search Page Data (`scrape_search`)

From search result pages, the scraper extracts the same property data structure as individual property pages, but from the search results listing.

---

## Summary Comparison

### Common Fields (Both Scrapers)
- Property ID/Listing ID
- Property Type
- Address (suburb, state, postcode)
- Description
- Property URL/Link
- Images/Media
- Bedrooms
- Bathrooms
- Parking
- Agent/Company Information
- Property Features

### Domain.com.au Unique Fields
- Schools information
- Suburb insights (demographics, market trends, sales history)
- Listing summary with pricing
- FAQs
- Gallery with multiple image sizes
- Loan finder information
- Structured features

### Realestate.com.au Unique Fields
- Geographic coordinates (latitude/longitude)
- Property sizes (land/building) with units
- Videos and floorplans
- Detailed property features with values
- Agent ratings and reviews
- Company ratings and reviews

---

## Notes

- Both scrapers handle pagination for search results
- Domain.com.au scraper uses Australian proxy (country: "AU")
- Realestate.com.au scraper uses US proxy (country: "US") with JavaScript rendering enabled
- Both scrapers use Scrapfly API for bypassing anti-scraping measures
- Data is extracted from hidden JSON data embedded in script tags on the pages
- Results are saved to JSON files in the `results/` directory of each scraper

