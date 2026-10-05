import json
from pathlib import Path
from typing import Literal

from ollama import RequestError, ResponseError, chat
from pydantic import BaseModel


INSTRUCTIONS_FILE = Path(__file__).with_name("news_ai_instructions.txt")


class NewsAnalysisError(Exception):
    pass


class NewsAnalysis(BaseModel):
    relevant: bool
    summary: str
    category: Literal[
        "Funding",
        "Product",
        "Partnership",
        "Leadership",
        "Market",
        "Legal",
        "Other",
    ]
    importance: Literal["Low", "Medium", "High"]
    why_it_matters: str
    confidence: Literal["Low", "Medium", "High"]


def analyze_news_article(company_name, article):
    instructions = INSTRUCTIONS_FILE.read_text(encoding="utf-8")
    article_for_analysis = {
        "tracked_company": company_name,
        "headline": article.get("title"),
        "description": article.get("description"),
        "source": article.get("source"),
        "published_at": article.get("published_at"),
        "source_country": article.get("source_country"),
        "provider": article.get("provider"),
        "url": article.get("url"),
    }

    try:
        response = chat(
            model="qwen3:8b",
            messages=[
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": json.dumps(article_for_analysis, indent=2),
                },
            ],
            think=False,
            format=NewsAnalysis.model_json_schema(),
            options={"temperature": 0},
        )
        analysis = NewsAnalysis.model_validate_json(response.message.content)
    except (RequestError, ResponseError, ValueError) as error:
        raise NewsAnalysisError(
            "The local AI could not analyze the news article."
        ) from error

    return analysis.model_dump()
