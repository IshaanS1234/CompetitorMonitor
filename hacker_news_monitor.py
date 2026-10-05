import json
from datetime import datetime, timedelta, timezone
import re
from pathlib import Path

import requests

from hacker_news_analyzer import (
    HackerNewsAnalysisError,
    analyze_hacker_news_discussion,
)
from news_monitor import load_tracked_companies


HACKER_NEWS_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
HACKER_NEWS_FOLDER = Path("hacker_news")


class HackerNewsMonitorError(Exception):
    pass


def normalized_title(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def company_history_file(company_name, filename, history_folder=HACKER_NEWS_FOLDER):
    safe_name = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
    return Path(history_folder) / safe_name / filename


def load_history(company_name, filename, history_folder=HACKER_NEWS_FOLDER):
    history_file = company_history_file(company_name, filename, history_folder)
    if not history_file.exists():
        return []

    try:
        records = json.loads(history_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise HackerNewsMonitorError(
            "The saved Hacker News history could not be read."
        ) from error

    if not isinstance(records, list):
        raise HackerNewsMonitorError(
            "The saved Hacker News history could not be read."
        )
    return records


def filter_unseen_discussions(company_name, discussions, history_folder=HACKER_NEWS_FOLDER):
    reviewed = load_history(company_name, "discussions.json", history_folder)
    reviewed += load_history(company_name, "rejected.json", history_folder)
    seen_urls = {record.get("discussion_url") for record in reviewed}
    seen_titles = {
        normalized_title(record.get("title", "")) for record in reviewed
    }

    return [
        discussion
        for discussion in discussions
        if discussion["discussion_url"] not in seen_urls
        and normalized_title(discussion["title"]) not in seen_titles
    ]


def analyze_discussions(company_name, discussions):
    relevant = []
    rejected = []

    for discussion in discussions:
        print(f"Analyzing: {discussion['title']}")
        try:
            analysis = analyze_hacker_news_discussion(company_name, discussion)
        except HackerNewsAnalysisError as error:
            print(error)
            continue

        reviewed_discussion = {**discussion, "ai_analysis": analysis}
        if analysis["relevant"]:
            relevant.append(reviewed_discussion)
        else:
            rejected.append(reviewed_discussion)

    return relevant, rejected


def save_discussions(
    company_name,
    discussions,
    filename,
    timestamp_name,
    history_folder=HACKER_NEWS_FOLDER,
):
    if not discussions:
        return []

    saved = load_history(company_name, filename, history_folder)
    seen_urls = {record.get("discussion_url") for record in saved}
    seen_titles = {normalized_title(record.get("title", "")) for record in saved}
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    new_records = []

    for discussion in discussions:
        title_key = normalized_title(discussion["title"])
        if discussion["discussion_url"] in seen_urls or title_key in seen_titles:
            continue

        new_records.append(
            {
                **discussion,
                "company": company_name,
                timestamp_name: timestamp,
            }
        )
        seen_urls.add(discussion["discussion_url"])
        seen_titles.add(title_key)

    if new_records:
        history_file = company_history_file(company_name, filename, history_folder)
        history_file.parent.mkdir(parents=True, exist_ok=True)
        history_file.write_text(
            json.dumps(new_records + saved, indent=2),
            encoding="utf-8",
        )

    return new_records


def search_hacker_news(company, days=30, result_limit=20):
    oldest_allowed = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        response = requests.get(
            HACKER_NEWS_SEARCH_URL,
            params={
                "query": company["domain"],
                "tags": "story",
                "numericFilters": f"created_at_i>{int(oldest_allowed.timestamp())}",
                "hitsPerPage": result_limit,
            },
            headers={
                "User-Agent": "CompetitorMonitor/0.1 (private local competitor monitor)"
            },
            timeout=30,
        )
        response.raise_for_status()
        hits = response.json().get("hits", [])
    except (requests.RequestException, ValueError) as error:
        raise HackerNewsMonitorError(
            "Hacker News search could not be reached."
        ) from error

    discussions = []
    seen_ids = set()
    seen_titles = set()

    for hit in hits:
        story_id = hit.get("objectID")
        title = hit.get("title") or hit.get("story_title")
        title_key = normalized_title(title or "")
        if (
            not story_id
            or not title
            or story_id in seen_ids
            or title_key in seen_titles
        ):
            continue

        seen_ids.add(story_id)
        seen_titles.add(title_key)
        discussions.append(
            {
                "company": company["name"],
                "title": title,
                "article_url": hit.get("url"),
                "discussion_url": f"https://news.ycombinator.com/item?id={story_id}",
                "author": hit.get("author", "Unknown"),
                "points": hit.get("points") or 0,
                "comment_count": hit.get("num_comments") or 0,
                "published_at": hit.get("created_at", "Unknown time"),
                "provider": "Hacker News",
            }
        )

    return discussions


def main():
    companies = load_tracked_companies()

    for company in companies:
        print(f"Searching Hacker News for {company['name']}...")
        try:
            discussions = search_hacker_news(company)
        except HackerNewsMonitorError as error:
            print(error)
            continue

        if not discussions:
            print("No recent discussions found.")
            continue

        unseen = filter_unseen_discussions(company["name"], discussions)
        if not unseen:
            print("No new discussions to analyze.")
            continue

        relevant, rejected = analyze_discussions(company["name"], unseen)
        saved_relevant = save_discussions(
            company["name"],
            relevant,
            "discussions.json",
            "discovered_at",
        )
        saved_rejected = save_discussions(
            company["name"],
            rejected,
            "rejected.json",
            "reviewed_at",
        )

        for discussion in saved_relevant:
            analysis = discussion["ai_analysis"]
            print(f"Saved: {discussion['title']}")
            print(
                f"  {analysis['category']} · "
                f"{analysis['importance']} importance · "
                f"{analysis['confidence']} confidence"
            )

        print(
            f"Saved {len(saved_relevant)} relevant and "
            f"{len(saved_rejected)} rejected discussions."
        )


if __name__ == "__main__":
    main()
