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
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
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


def generate_content_tool(research_data_json: str) -> str:
    """
    Generate museum-appropriate content for an artwork based on research data.

    This function is used as a tool by the LangChain agent.
    It takes research data as JSON string and generates engaging content.

    Args:
        research_data_json: JSON string containing artwork research data

    Returns:
        Generated content text, or error message if failed
    """
    import json
    try:
        research_dict = json.loads(research_data_json)

        llm = ChatGroq(
            model_name="llama-3.1-8b-instant",
            groq_api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.7
        )

        prompt_text = f"""You are a professional museum content writer for the Metropolitan Museum of Art.
Generate an engaging, educational, and museum-appropriate description (100-200 words) for this artwork:

Title: {research_dict.get('title', 'Unknown')}
Artist: {research_dict.get('artist_display_name', 'Unknown Artist')}
Date: {research_dict.get('object_date', 'Unknown Date')}
Department: {research_dict.get('department', 'Unknown Department')}
Culture: {research_dict.get('culture', 'Unknown Culture')}
Period: {research_dict.get('period', 'Unknown Period')}
Medium: {research_dict.get('medium', 'Unknown Medium')}
Dimensions: {research_dict.get('dimensions', 'Unknown Dimensions')}
Artist Bio: {research_dict.get('artist_display_bio', 'No biography available')}
Nationality: {research_dict.get('artist_nationality', 'Unknown')}
Classification: {research_dict.get('classification', 'Unknown')}
Object Name: {research_dict.get('object_name', 'Unknown')}

Guidelines:
- Write 100-200 words
- Use a professional but accessible tone
- Make it engaging for museum visitors
- Include historical context, artistic techniques, and cultural significance
- Be accurate and fact-based
- Avoid overly technical language
- Make the artwork come alive for the reader
- Focus on what makes this artwork special and noteworthy

Generate the description now:"""

        response = llm.invoke(prompt_text)
        return response.content

    except Exception as e:
        return f"Error generating content: {str(e)}"


generate_content_tool_obj = Tool(
    name="generate_content",
    func=generate_content_tool,
    description=(
        "Generate museum-appropriate content (100-200 words) for an artwork. "
        "Input should be a JSON string containing artwork research data. "
        "Example: '{\"title\": \"Artwork Title\", \"artist_display_name\": \"Artist Name\", "
        "\"object_date\": \"1853\", \"department\": \"Department Name\", "
        "\"culture\": \"Culture\", \"period\": \"Period\", \"medium\": \"Medium\", "
        "\"dimensions\": \"Dimensions\", \"artist_display_bio\": \"Bio\", "
        "\"artist_nationality\": \"Nationality\", \"classification\": \"Classification\", "
        "\"object_name\": \"Object Name\"}'"
    )
)

tools = [generate_content_tool_obj]

llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    groq_api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.7
)

prompt = ChatPromptTemplate.from_messages(
    [
            (
            "system",
            """You are a professional museum content writer for the Metropolitan Museum of Art.
            Your task is to create engaging, educational, and museum-appropriate descriptions
            for artworks based on research data.

            When given artwork research data, you MUST use the generate_content tool to create
            a 100-200 word description. Pass the research data as a JSON string to the tool.

            Always use the generate_content tool - it will handle the content generation for you.
            """
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

agent = create_tool_calling_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True
)


class ContentGenerationAgent:
    """
    Content Generation Agent class that uses LangChain and Groq with AgentExecutor
    to generate engaging museum-appropriate descriptions for artworks.
    """

    def __init__(self):
        """Initialize the Content Generation Agent."""
        self.agent_executor = agent_executor
        self.llm = llm
        self.tools = tools

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
        import json

        try:
            research_dict = {
                "title": research_data.title or "Unknown",
                "artist_display_name": research_data.artist_display_name or "Unknown Artist",
                "object_date": research_data.object_date or "Unknown Date",
                "department": research_data.department or "Unknown Department",
                "culture": research_data.culture or "Unknown Culture",
                "period": research_data.period or "Unknown Period",
                "medium": research_data.medium or "Unknown Medium",
                "dimensions": research_data.dimensions or "Unknown Dimensions",
                "artist_display_bio": research_data.artist_display_bio or "No biography available",
                "artist_nationality": research_data.artist_nationality or "Unknown",
                "classification": research_data.classification or "Unknown",
                "object_name": research_data.object_name or "Unknown"
            }

            research_json = json.dumps(research_dict)
            query = f"Generate museum-appropriate content (100-200 words) for this artwork using the generate_content tool. Research data: {research_json}"

            try:
                result = self.agent_executor.invoke({"input": query})
                generated_text = result.get("output", "")

                if not generated_text or len(generated_text) < 100:
                    generated_text = generate_content_tool(research_json)
            except Exception as e:
                print(f"AgentExecutor error, using direct tool call: {e}")
                generated_text = generate_content_tool(research_json)

            if "Error" in generated_text:
                print(f"Error: {generated_text}")
                return None

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

