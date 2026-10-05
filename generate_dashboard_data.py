import json
from datetime import datetime
from pathlib import Path


PROJECT_FOLDER = Path(__file__).resolve().parent
SNAPSHOTS_FOLDER = PROJECT_FOLDER / "snapshots"
EVENTS_FOLDER = PROJECT_FOLDER / "events"
REPORTS_FOLDER = PROJECT_FOLDER / "reports"
NEWS_FOLDER = PROJECT_FOLDER / "news"
HACKER_NEWS_FOLDER = PROJECT_FOLDER / "hacker_news"
DASHBOARD_DATA_FILE = PROJECT_FOLDER / "dashboard" / "public" / "monitor-data.json"


def display_name(value):
    return value.replace("_", " ").replace("-", " ").title()


def normalize_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return value

    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.isoformat(timespec="seconds")


def parse_report(report_path):
    report_text = report_path.read_text(encoding="utf-8")
    run_line = next(
        (line for line in report_text.splitlines() if line.startswith("Run: ")),
        "Run: Unknown",
    )
    change_count = sum(
        line.startswith("Change detected on ") for line in report_text.splitlines()
    )
    return {
        "run_at": normalize_timestamp(run_line.removeprefix("Run: ")),
        "status": "Changes found" if change_count else "No changes",
        "change_count": change_count,
        "report_file": str(report_path.relative_to(PROJECT_FOLDER)),
    }


def load_events():
    events = []
    if not EVENTS_FOLDER.exists():
        return events

    for event_path in EVENTS_FOLDER.glob("**/*.json"):
        try:
            event = json.loads(event_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        analysis = event.get("ai_analysis") or {}
        events.append(
            {
                "company": event.get("company", "Unknown company"),
                "page": display_name(event.get("page", "Unknown page")),
                "detected_at": normalize_timestamp(
                    event.get("detected_at", "Unknown time")
                ),
                "summary": analysis.get("summary", event.get("summary", "Change detected")),
                "importance": analysis.get("importance", "Unknown"),
                "category": analysis.get("category", event.get("category", "Other")),
                "why_it_matters": analysis.get("why_it_matters", "Analysis unavailable"),
            }
        )

    return sorted(events, key=lambda event: event["detected_at"], reverse=True)


def load_news_articles():
    articles = []
    if not NEWS_FOLDER.exists():
        return articles

    for articles_path in NEWS_FOLDER.glob("*/articles.json"):
        try:
            saved_articles = json.loads(articles_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(saved_articles, list):
            continue

        for article in saved_articles:
            analysis = article.get("ai_analysis") or {}
            if analysis.get("relevant") is False:
                continue

            articles.append(
                {
                    "company": article.get("company", "Unknown company"),
                    "title": article.get("title", "Untitled article"),
                    "url": article.get("url", ""),
                    "source": article.get("source", "Unknown source"),
                    "published_at": normalize_timestamp(
                        article.get("published_at", "Unknown time")
                    ),
                    "provider": article.get("provider", "Unknown provider"),
                    "discovered_at": normalize_timestamp(
                        article.get("discovered_at", "Unknown time")
                    ),
                    "summary": analysis.get("summary", "Analysis unavailable"),
                    "category": analysis.get("category", "Other"),
                    "importance": analysis.get("importance", "Unknown"),
                    "why_it_matters": analysis.get(
                        "why_it_matters", "Analysis unavailable"
                    ),
                    "confidence": analysis.get("confidence", "Unknown"),
                }
            )

    return sorted(
        articles,
        key=lambda article: article["discovered_at"],
        reverse=True,
    )


def load_hacker_news_discussions():
    discussions = []
    if not HACKER_NEWS_FOLDER.exists():
        return discussions

    for discussions_path in HACKER_NEWS_FOLDER.glob("*/discussions.json"):
        try:
            saved_discussions = json.loads(
                discussions_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(saved_discussions, list):
            continue

        for discussion in saved_discussions:
            analysis = discussion.get("ai_analysis") or {}
            if analysis.get("relevant") is False:
                continue

            discussions.append(
                {
                    "company": discussion.get("company", "Unknown company"),
                    "title": discussion.get("title", "Untitled discussion"),
                    "article_url": discussion.get("article_url", ""),
                    "discussion_url": discussion.get("discussion_url", ""),
                    "author": discussion.get("author", "Unknown"),
                    "points": discussion.get("points", 0),
                    "comment_count": discussion.get("comment_count", 0),
                    "published_at": normalize_timestamp(
                        discussion.get("published_at", "Unknown time")
                    ),
                    "discovered_at": normalize_timestamp(
                        discussion.get("discovered_at", "Unknown time")
                    ),
                    "summary": analysis.get("summary", "Analysis unavailable"),
                    "category": analysis.get("category", "Other"),
                    "importance": analysis.get("importance", "Unknown"),
                    "why_it_matters": analysis.get(
                        "why_it_matters", "Analysis unavailable"
                    ),
                    "confidence": analysis.get("confidence", "Unknown"),
                }
            )

    return sorted(
        discussions,
        key=lambda discussion: discussion["discovered_at"],
        reverse=True,
    )


def build_dashboard_data():
    companies = []
    if SNAPSHOTS_FOLDER.exists():
        for company_folder in sorted(path for path in SNAPSHOTS_FOLDER.iterdir() if path.is_dir()):
            pages = []
            for page_folder in sorted(path for path in company_folder.iterdir() if path.is_dir()):
                snapshots = sorted(page_folder.glob("snapshot_*.txt"))
                if not snapshots:
                    continue
                latest_snapshot = snapshots[-1]
                pages.append(
                    {
                        "name": display_name(page_folder.name),
                        "snapshot_count": len(snapshots),
                        "last_checked": datetime.fromtimestamp(
                            latest_snapshot.stat().st_mtime
                        ).astimezone().isoformat(timespec="seconds"),
                    }
                )

            if pages:
                companies.append(
                    {
                        "name": display_name(company_folder.name.split(".")[0]),
                        "domain": company_folder.name,
                        "pages": pages,
                    }
                )

    report_paths = sorted(REPORTS_FOLDER.glob("report_*.txt"), reverse=True)
    recent_runs = [parse_report(path) for path in report_paths[:5]]
    events = load_events()
    news_articles = load_news_articles()
    hacker_news_discussions = load_hacker_news_discussions()
    page_count = sum(len(company["pages"]) for company in companies)

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "overview": {
            "company_count": len(companies),
            "page_count": page_count,
            "change_count": len(events),
            "news_count": len(news_articles),
            "hacker_news_count": len(hacker_news_discussions),
            "latest_status": recent_runs[0]["status"] if recent_runs else "Not run yet",
        },
        "companies": companies,
        "recent_runs": recent_runs,
        "recent_news": news_articles[:10],
        "recent_hacker_news": hacker_news_discussions[:10],
        "recent_changes": events[:10],
    }


def main():
    DASHBOARD_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = build_dashboard_data()
    DASHBOARD_DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Updated dashboard data: {DASHBOARD_DATA_FILE}")


if __name__ == "__main__":
    main()
