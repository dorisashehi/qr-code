"""
Quality Assurance Agent for MET Museum Artworks

This agent reviews generated content for factual accuracy, tone,
readability, and appropriateness before it's published.
"""
import os
import sys
from pathlib import Path
from typing import Optional
from enum import Enum

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from agents.research_agent import ResearchResponse
from agents.content_generation_agent import GeneratedContent

load_dotenv()


class QAStatus(str, Enum):
    """Quality assurance status values."""
    PASSED = "passed"
    FAILED = "failed"
    REVIEW = "review"
    PENDING = "pending"


class QAResponse(BaseModel):
    """
    Quality assurance response from the QA agent.
    """
    artwork_id: int = Field(description="Database ID of the artwork")
    met_object_id: int = Field(description="MET Museum object ID")
    qa_status: QAStatus = Field(description="QA status: passed, failed, or review")
    factual_accuracy: bool = Field(description="Whether content is factually accurate")
    museum_tone: bool = Field(description="Whether tone is museum-appropriate")
    readability: bool = Field(description="Whether content is readable")
    no_problematic_language: bool = Field(description="Whether content has no problematic language")
    notes: str = Field(description="Detailed notes about the QA review")
    needs_human_review: bool = Field(description="Whether content needs human review")


llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    groq_api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1
)

def review_content_tool(qa_data_json: str) -> str:
    """
    Review generated content for quality assurance.

    This function is used as a tool by the LangChain agent.
    It reviews content for accuracy, tone, readability, and appropriateness.

    Args:
        qa_data_json: JSON string containing artwork metadata and generated content

    Returns:
        QA review text with assessment, or error message if failed
    """
    import json
    try:
        qa_dict = json.loads(qa_data_json)

        llm = ChatGroq(
            model_name="llama-3.1-8b-instant",
            groq_api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1
        )

        prompt_text = f"""You are a quality assurance reviewer for the Metropolitan Museum of Art.
Review the following generated content for artwork and ensure it meets museum standards.

Artwork Metadata:
Title: {qa_dict.get('title', 'Unknown')}
Artist: {qa_dict.get('artist', 'Unknown Artist')}
Date: {qa_dict.get('date', 'Unknown Date')}
Department: {qa_dict.get('department', 'Unknown Department')}
Culture: {qa_dict.get('culture', 'Unknown Culture')}
Period: {qa_dict.get('period', 'Unknown Period')}
Medium: {qa_dict.get('medium', 'Unknown Medium')}
Artist Bio: {qa_dict.get('artist_bio', 'No biography available')}
Nationality: {qa_dict.get('nationality', 'Unknown')}
Classification: {qa_dict.get('classification', 'Unknown')}

Generated Content:
{qa_dict.get('generated_content', '')}

Review the content for:
1. Factual Accuracy: Cross-reference with the artwork metadata. Check that dates, names, locations, and facts match.
2. Museum-Appropriate Tone: Ensure the tone is professional, educational, and suitable for a museum audience.
3. Readability: Check that the content is clear, well-structured, and easy to understand.
4. No Problematic Language: Ensure there's no offensive, biased, or inappropriate language.

Return your assessment with:
- factual_accuracy: true/false
- museum_tone: true/false
- readability: true/false
- no_problematic_language: true/false
- qa_status: "passed" if all checks pass, "failed" if critical issues, "review" if minor issues
- needs_human_review: true if there are any concerns
- notes: Detailed explanation of your findings

Provide a comprehensive QA review:"""

        response = llm.invoke(prompt_text)
        return response.content

    except Exception as e:
        return f"Error reviewing content: {str(e)}"


review_content_tool_obj = Tool(
    name="review_content",
    func=review_content_tool,
    description=(
        "Review generated content for quality assurance. "
        "Input should be a JSON string containing artwork metadata and generated content. "
        "Example: '{{\"title\": \"Artwork Title\", \"artist\": \"Artist Name\", "
        "\"date\": \"1853\", \"department\": \"Department\", \"culture\": \"Culture\", "
        "\"period\": \"Period\", \"medium\": \"Medium\", \"artist_bio\": \"Bio\", "
        "\"nationality\": \"Nationality\", \"classification\": \"Classification\", "
        "\"generated_content\": \"Content to review\"}'"
    )
)

tools = [review_content_tool_obj]

llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    groq_api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1
)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a quality assurance reviewer for the Metropolitan Museum of Art.
            Your task is to review generated content for artworks and ensure it meets
            museum standards before publication.

            When given artwork metadata and generated content, you MUST use the review_content
            tool to perform a comprehensive QA review. The tool will check for:
            - Factual accuracy
            - Museum-appropriate tone
            - Readability
            - No problematic language

            Always use the review_content tool to perform the review."""
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


class QualityAssuranceAgent:
    """
    Quality Assurance Agent class that reviews generated content
    for accuracy, tone, readability, and appropriateness.
    """

    def __init__(self):
        """Initialize the Quality Assurance Agent."""
        self.agent_executor = agent_executor
        self.llm = llm
        self.tools = tools

    def review_content(
        self,
        generated_content: GeneratedContent,
        research_data: ResearchResponse
    ) -> Optional[QAResponse]:
        """
        Review generated content for quality assurance.

        Args:
            generated_content: GeneratedContent object with the content to review
            research_data: ResearchResponse object with artwork metadata for verification

        Returns:
            QAResponse with QA status and notes, or None if error
        """
        import json

        try:
            qa_dict = {
                "title": research_data.title or "Unknown",
                "artist": research_data.artist_display_name or "Unknown Artist",
                "date": research_data.object_date or "Unknown Date",
                "department": research_data.department or "Unknown Department",
                "culture": research_data.culture or "Unknown Culture",
                "period": research_data.period or "Unknown Period",
                "medium": research_data.medium or "Unknown Medium",
                "artist_bio": research_data.artist_display_bio or "No biography available",
                "nationality": research_data.artist_nationality or "Unknown",
                "classification": research_data.classification or "Unknown",
                "generated_content": generated_content.content
            }

            qa_json = json.dumps(qa_dict)
            query = f"Review the generated content for quality assurance. Use the review_content tool with this data: {qa_json}"

            try:
                result = self.agent_executor.invoke({"input": query})
                review_text = result.get("output", "")

                if not review_text or len(review_text) < 50:
                    review_text = review_content_tool(qa_json)
            except Exception as e:
                print(f"AgentExecutor error, using direct tool call: {e}")
                review_text = review_content_tool(qa_json)

            if "Error" in review_text:
                print(f"Error: {review_text}")
                return None

            qa_result = self._parse_qa_response(review_text, generated_content, research_data)

            return qa_result

        except Exception as e:
            print(f"Error in quality assurance agent: {e}")
            return None

    def _parse_qa_response(
        self,
        review_text: str,
        generated_content: GeneratedContent,
        research_data: ResearchResponse
    ) -> QAResponse:
        """
        Parse the LLM response and extract QA information.

        Args:
            review_text: The LLM's review text
            generated_content: The generated content being reviewed
            research_data: The research data for reference

        Returns:
            QAResponse with parsed QA information
        """
        review_lower = review_text.lower()

        factual_accuracy = (
            "factual_accuracy" in review_lower and "true" in review_lower
        ) or ("accurate" in review_lower and "inaccurate" not in review_lower)

        museum_tone = (
            "museum_tone" in review_lower and "true" in review_lower
        ) or ("appropriate" in review_lower and "inappropriate" not in review_lower)

        readability = (
            "readability" in review_lower and "true" in review_lower
        ) or ("readable" in review_lower or "clear" in review_lower)

        no_problematic_language = (
            "no_problematic_language" in review_lower and "true" in review_lower
        ) or ("problematic" not in review_lower or ("no" in review_lower and "problematic" in review_lower))

        if "qa_status" in review_lower or "status" in review_lower:
            if "passed" in review_lower:
                qa_status = QAStatus.PASSED
            elif "failed" in review_lower:
                qa_status = QAStatus.FAILED
            else:
                qa_status = QAStatus.REVIEW
        else:
            if all([factual_accuracy, museum_tone, readability, no_problematic_language]):
                qa_status = QAStatus.PASSED
            elif not factual_accuracy or not no_problematic_language:
                qa_status = QAStatus.FAILED
            else:
                qa_status = QAStatus.REVIEW

        needs_human_review = (
            qa_status == QAStatus.REVIEW or
            qa_status == QAStatus.FAILED or
            not factual_accuracy or
            not museum_tone or
            not no_problematic_language
        )

        return QAResponse(
            artwork_id=generated_content.artwork_id,
            met_object_id=generated_content.met_object_id,
            qa_status=qa_status,
            factual_accuracy=factual_accuracy,
            museum_tone=museum_tone,
            readability=readability,
            no_problematic_language=no_problematic_language,
            notes=review_text,
            needs_human_review=needs_human_review
        )


if __name__ == "__main__":
    from agents.research_agent import ResearchAgent
    from agents.content_generation_agent import ContentGenerationAgent

    print("Testing Quality Assurance Agent...")
    print("=" * 50)

    research_agent = ResearchAgent()
    artwork_research = research_agent.research(met_object_id=1)

    if artwork_research:
        print(f"\n✓ Research data retrieved for: {artwork_research.title}")

        content_agent = ContentGenerationAgent()
        generated = content_agent.generate_content(artwork_research)

        if generated:
            print(f"✓ Content generated ({generated.word_count} words)")

            print("\nRunning QA review...")
            print("-" * 50)

            qa_agent = QualityAssuranceAgent()
            qa_result = qa_agent.review_content(generated, artwork_research)

            if qa_result:
                print(f"\n✓ QA Review Complete!")
                print(f"  Status: {qa_result.qa_status.value}")
                print(f"  Factual Accuracy: {'✓' if qa_result.factual_accuracy else '✗'}")
                print(f"  Museum Tone: {'✓' if qa_result.museum_tone else '✗'}")
                print(f"  Readability: {'✓' if qa_result.readability else '✗'}")
                print(f"  No Problematic Language: {'✓' if qa_result.no_problematic_language else '✗'}")
                print(f"  Needs Human Review: {'Yes' if qa_result.needs_human_review else 'No'}")
                print(f"\nQA Notes:")
                print("=" * 50)
                print(qa_result.notes)
                print("=" * 50)
            else:
                print("\n✗ Failed to complete QA review.")
        else:
            print("\n✗ Failed to generate content.")
    else:
        print("\n✗ No research data found. Make sure your database has artwork data.")

