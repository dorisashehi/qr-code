"""
Research Agent for MET Museum Artworks

This agent uses LangChain and Groq LLM to fetch and research artwork
metadata from the database. It returns structured data for content generation.
"""
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from database.database import get_db_session
from database.models import Artwork

load_dotenv()


class ResearchResponse(BaseModel):
    """
    Structured research data that the agent returns.
    This contains all the artwork information needed for content generation.
    """
    artwork_id: int = Field(description="Database ID of the artwork")
    met_object_id: int = Field(description="MET Museum object ID")
    title: Optional[str] = Field(None, description="Title of the artwork")
    object_name: Optional[str] = Field(
        None, description="Type of object (e.g., 'Painting', 'Sculpture')"
    )
    artist_display_name: Optional[str] = Field(None, description="Name of the artist")
    artist_display_bio: Optional[str] = Field(
        None, description="Biography of the artist"
    )
    artist_nationality: Optional[str] = Field(
        None, description="Nationality of the artist"
    )
    artist_gender: Optional[str] = Field(None, description="Gender of the artist")
    object_date: Optional[str] = Field(
        None, description="Date string (e.g., 'ca. 1503-1519')"
    )
    object_begin_date: Optional[int] = Field(
        None, description="Start year of creation"
    )
    object_end_date: Optional[int] = Field(None, description="End year of creation")
    period: Optional[str] = Field(None, description="Historical period")
    dynasty: Optional[str] = Field(
        None, description="Dynasty (for ancient artworks)"
    )
    culture: Optional[str] = Field(None, description="Cultural origin")
    department: Optional[str] = Field(None, description="Museum department")
    classification: Optional[str] = Field(
        None, description="Artwork classification"
    )
    medium: Optional[str] = Field(
        None, description="Materials used (e.g., 'Oil on canvas')"
    )
    dimensions: Optional[str] = Field(None, description="Physical dimensions")
    constituents: Optional[Any] = Field(
        None, description="Multiple artists or contributors (JSON - can be list or dict)"
    )
    is_public_domain: bool = Field(False, description="Whether artwork is in public domain")
    primary_image: Optional[str] = Field(None, description="URL to primary image")
    object_url: Optional[str] = Field(None, description="URL to artwork page on MET website")


def fetch_artwork_by_met_id(met_object_id: int) -> Dict[str, Any]:
    """
    Fetch artwork from database by MET Museum object ID.

    This function is used as a tool by the LangChain agent.
    It queries the database using the MET object ID.

    Args:
        met_object_id: The MET Museum object ID

    Returns:
        Dictionary with artwork data, or error message if not found
    """
    try:
        with get_db_session() as db:
            artwork = db.query(Artwork).filter(
                Artwork.met_object_id == met_object_id
            ).first()

            if artwork is None:
                return {
                    "error": f"Artwork with MET ID {met_object_id} not found",
                    "found": False
                }

            artwork_data = {
                "found": True,
                "artwork_id": artwork.id,
                "met_object_id": artwork.met_object_id,
                "title": artwork.title,
                "object_name": artwork.object_name,
                "artist_display_name": artwork.artist_display_name,
                "artist_display_bio": artwork.artist_display_bio,
                "artist_nationality": artwork.artist_nationality,
                "artist_gender": artwork.artist_gender,
                "object_date": artwork.object_date,
                "object_begin_date": artwork.object_begin_date,
                "object_end_date": artwork.object_end_date,
                "period": artwork.period,
                "dynasty": artwork.dynasty,
                "culture": artwork.culture,
                "department": artwork.department,
                "classification": artwork.classification,
                "medium": artwork.medium,
                "dimensions": artwork.dimensions,
                "constituents": artwork.constituents if artwork.constituents else None,
                "is_public_domain": artwork.is_public_domain,
                "primary_image": artwork.primary_image,
                "object_url": artwork.object_url,
            }

            return artwork_data

    except Exception as e:
        return {
            "error": f"Error fetching artwork: {str(e)}",
            "found": False
        }


artwork_by_met_id_tool = Tool(
    name="fetch_artwork_by_met_id",
    func=fetch_artwork_by_met_id,
    description=(
        "Fetch artwork from database using the MET Museum object ID. "
        "Input should be an integer MET object ID."
    )
)

tools = [artwork_by_met_id_tool]

llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    groq_api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1
)

parser = PydanticOutputParser(pydantic_object=ResearchResponse)

llm_with_tools = llm.bind_tools(tools)


class ResearchAgent:
    """
    Research Agent class that uses LangChain and Groq to research artworks.

    This agent can fetch artwork information from the database and return
    it in a structured format for use by other agents in the pipeline.
    """

    def __init__(self):
        """Initialize the Research Agent."""
        self.llm = llm_with_tools
        self.tools = tools

    def research(
        self,
        met_object_id: int
    ) -> Optional[ResearchResponse]:
        """
        Research an artwork and return structured data.

        Args:
            met_object_id: MET Museum object ID

        Returns:
            ResearchResponse with artwork data, or None if not found
        """
        try:
            artwork_data = fetch_artwork_by_met_id(met_object_id)

            if not artwork_data.get("found", False):
                error_msg = artwork_data.get('error', 'Unknown error')
                print(f"Artwork not found: {error_msg}")
                return None

            research_response = ResearchResponse(
                artwork_id=artwork_data["artwork_id"],
                met_object_id=artwork_data["met_object_id"],
                title=artwork_data.get("title"),
                object_name=artwork_data.get("object_name"),
                artist_display_name=artwork_data.get("artist_display_name"),
                artist_display_bio=artwork_data.get("artist_display_bio"),
                artist_nationality=artwork_data.get("artist_nationality"),
                artist_gender=artwork_data.get("artist_gender"),
                object_date=artwork_data.get("object_date"),
                object_begin_date=artwork_data.get("object_begin_date"),
                object_end_date=artwork_data.get("object_end_date"),
                period=artwork_data.get("period"),
                dynasty=artwork_data.get("dynasty"),
                culture=artwork_data.get("culture"),
                department=artwork_data.get("department"),
                classification=artwork_data.get("classification"),
                medium=artwork_data.get("medium"),
                dimensions=artwork_data.get("dimensions"),
                constituents=artwork_data.get("constituents"),
                is_public_domain=artwork_data.get("is_public_domain", False),
                primary_image=artwork_data.get("primary_image"),
                object_url=artwork_data.get("object_url"),
            )

            return research_response

        except Exception as e:
            print(f"Error in research agent: {e}")
            return None


if __name__ == "__main__":
    research_agent = ResearchAgent()

    print("Testing Research Agent...")
    print("=" * 50)

    result = research_agent.research(met_object_id=1)

    if result:
        print(f"\n✓ Found artwork: {result.title}")
        print(f"  Artist: {result.artist_display_name}")
        print(f"  Department: {result.department}")
        print(f"  Date: {result.object_date}")
        print("\nFull research data:")
        print(result.model_dump_json(indent=2))
    else:
        print("\n✗ No artwork found. Make sure your database has artwork data.")
        print("  You can sync artworks using: python scripts/sync_met_artworks.py")
