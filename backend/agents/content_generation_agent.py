"""
Content Generation Agent for MET Museum Artworks

This agent uses LangChain and Groq LLM to generate engaging,
museum-appropriate descriptions for artworks based on research data.
"""
import os
import sys
from pathlib import Path
from typing import Optional

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from agents.research_agent import ResearchResponse

load_dotenv()


class GeneratedContent(BaseModel):
    """
    Generated content response from the content generation agent.
    """
    artwork_id: int = Field(description="Database ID of the artwork")
    met_object_id: int = Field(description="MET Museum object ID")
    content: str = Field(description="Generated museum-appropriate description (100-200 words)")
    word_count: int = Field(description="Number of words in the generated content")


llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    groq_api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.7
)

prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a professional museum content writer for the Metropolitan Museum of Art.
            Your task is to create engaging, educational, and museum-appropriate descriptions
            for artworks based on the research data provided.

            Guidelines:
            - Write 100-200 words
            - Use a professional but accessible tone
            - Make it engaging for museum visitors
            - Include historical context, artistic techniques, and cultural significance
            - Be accurate and fact-based
            - Avoid overly technical language
            - Make the artwork come alive for the reader
            - Focus on what makes this artwork special and noteworthy
            """
        ),
        (
            "human",
            """Generate a museum-appropriate description for the following artwork:

Title: {title}
Artist: {artist}
Date: {date}
Department: {department}
Culture: {culture}
Period: {period}
Medium: {medium}
Dimensions: {dimensions}
Artist Bio: {artist_bio}
Nationality: {nationality}
Classification: {classification}
Object Name: {object_name}

Please create an engaging 100-200 word description that would be suitable
for display in a museum gallery or on a museum website."""
        ),
    ]
)


class ContentGenerationAgent:
    """
    Content Generation Agent class that uses LangChain and Groq to generate
    engaging museum-appropriate descriptions for artworks.
    """

    def __init__(self):
        """Initialize the Content Generation Agent."""
        self.llm = llm
        self.prompt = prompt_template

    def generate_content(
        self,
        research_data: ResearchResponse
    ) -> Optional[GeneratedContent]:
        """
        Generate engaging museum-appropriate content for an artwork.

        Args:
            research_data: ResearchResponse object with artwork information

        Returns:
            GeneratedContent with the generated description, or None if error
        """
        try:
            formatted_prompt = self.prompt.format_messages(
                title=research_data.title or "Unknown",
                artist=research_data.artist_display_name or "Unknown Artist",
                date=research_data.object_date or "Unknown Date",
                department=research_data.department or "Unknown Department",
                culture=research_data.culture or "Unknown Culture",
                period=research_data.period or "Unknown Period",
                medium=research_data.medium or "Unknown Medium",
                dimensions=research_data.dimensions or "Unknown Dimensions",
                artist_bio=research_data.artist_display_bio or "No biography available",
                nationality=research_data.artist_nationality or "Unknown",
                classification=research_data.classification or "Unknown",
                object_name=research_data.object_name or "Unknown"
            )

            response = self.llm.invoke(formatted_prompt)
            generated_text = response.content

            word_count = len(generated_text.split())

            generated_content = GeneratedContent(
                artwork_id=research_data.artwork_id,
                met_object_id=research_data.met_object_id,
                content=generated_text,
                word_count=word_count
            )

            return generated_content

        except Exception as e:
            print(f"Error in content generation agent: {e}")
            return None


if __name__ == "__main__":
    from agents.research_agent import ResearchAgent

    print("Testing Content Generation Agent...")
    print("=" * 50)

    research_agent = ResearchAgent()
    artwork_research = research_agent.research(met_object_id=1)

    if artwork_research:
        print(f"\n✓ Research data retrieved for: {artwork_research.title}")
        print(f"  Artist: {artwork_research.artist_display_name}")
        print("\nGenerating content...")
        print("-" * 50)

        content_agent = ContentGenerationAgent()
        generated = content_agent.generate_content(artwork_research)

        if generated:
            print("\n✓ Content generated successfully!")
            print(f"  Word count: {generated.word_count}")
            print("\nGenerated Content:")
            print("=" * 50)
            print(generated.content)
            print("=" * 50)
        else:
            print("\n✗ Failed to generate content.")
    else:
        print("\n✗ No research data found. Make sure your database has artwork data.")

