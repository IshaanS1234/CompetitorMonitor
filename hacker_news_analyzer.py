import json
from pathlib import Path
from typing import Literal

from ollama import RequestError, ResponseError, chat
from pydantic import BaseModel


INSTRUCTIONS_FILE = Path(__file__).with_name("hacker_news_ai_instructions.txt")


class HackerNewsAnalysisError(Exception):
    pass


class HackerNewsAnalysis(BaseModel):
    relevant: bool
    summary: str
    category: Literal[
        "Product",
        "Engineering",
        "Funding",
        "Hiring",
        "Leadership",
        "Market",
        "Community",
        "Other",
    ]
    importance: Literal["Low", "Medium", "High"]
    why_it_matters: str
    confidence: Literal["Low", "Medium", "High"]


def analyze_hacker_news_discussion(company_name, discussion):
    instructions = INSTRUCTIONS_FILE.read_text(encoding="utf-8")
    discussion_for_analysis = {
        "tracked_company": company_name,
        "title": discussion.get("title"),
        "author": discussion.get("author"),
        "points": discussion.get("points"),
        "comment_count": discussion.get("comment_count"),
        "published_at": discussion.get("published_at"),
        "article_url": discussion.get("article_url"),
        "discussion_url": discussion.get("discussion_url"),
    }

    try:
        response = chat(
            model="qwen3:8b",
            messages=[
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": json.dumps(discussion_for_analysis, indent=2),
                },
            ],
            think=False,
            format=HackerNewsAnalysis.model_json_schema(),
            options={"temperature": 0},
        )
        analysis = HackerNewsAnalysis.model_validate_json(response.message.content)
    except (RequestError, ResponseError, ValueError) as error:
        raise HackerNewsAnalysisError(
            "The local AI could not analyze the Hacker News discussion."
        ) from error

    return analysis.model_dump()
