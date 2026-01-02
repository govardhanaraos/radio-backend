# stations/models.py
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional

class Station(BaseModel):
    """
    Defines the structure of a radio station, mapping MongoDB fields 
    to Pydantic/Python fields for validation.
    """
    # MongoDB's _id is often excluded from the response, but if included, it's handled like this:
    # id_str: str = Field(..., alias="_id") 

    # 1. Primary ID field (matches "id": "0001" in the screenshot)
    id: str = Field(..., description="The application's unique ID for the station.")

    # 2. Main fields
    name: str

    # 3. Logo URL (Maps from logoUrl in Mongo)
    # Using alias="logoUrl" ensures Pydantic can read the Mongo field name
    logo_url: Optional[HttpUrl] = Field(None, alias="logoUrl")

    # 4. Stream URL (Maps from streamUrl in Mongo)
    stream_url: HttpUrl = Field(..., alias="streamUrl")

    # 5. Language (Maps from Language in Mongo)
    # Note: Python convention is lowercase, but we match the capital 'L' in the alias
    language: Optional[str] = Field(None, alias="Language")

    # 6. Genre (Maps from genre in Mongo)
    genre: Optional[str] = None

    # 7. Page field (Maps from page in Mongo)
    page: Optional[str] = None

    # Configuration to allow reading field names that use underscores (like logo_url)
    # while still allowing mapping from the MongoDB field names.
    class Config:
        populate_by_name = True
        # allows conversion to json from mongo fields names e.g., 'logoUrl'
        json_encoders = {
            # You may need to add ObjectId encoder here if returning _id
        }

class StationFilter(BaseModel):
    """
    Defines optional query parameters for filtering the station list.
    FastAPI will automatically convert URL query parameters
    (e.g., ?language=english&genre=pop) into this object.
    """
    # Use Optional to make all fields optional for filtering
    language: Optional[str] = Field(None, alias="Language")
    genre: Optional[str] = None

    # Add any other optional fields you want to filter by (e.g., page)
    page: int = 1
    limit: int = 50
    class Config:
        # Allows Pydantic to match 'Language' field name from URL query or JSON body
        populate_by_name = True