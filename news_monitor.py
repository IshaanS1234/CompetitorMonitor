import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests

from news_analyzer import NewsAnalysisError, analyze_news_article


GDELT_SEARCH_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
TRACKED_PAGES_FILE = Path("tracked_pages.txt")
NEWS_FOLDER = Path("news")


class NewsMonitorError(Exception):
    pass


def company_name_from_url(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    domain = urlparse(url).netloc.removeprefix("www.")
    return domain.split(".")[0].replace("-", " ").title()


def load_tracked_companies(tracked_pages_file=TRACKED_PAGES_FILE):
    tracked_pages_file = Path(tracked_pages_file)
    if not tracked_pages_file.exists():
        raise NewsMonitorError("The tracked_pages.txt file could not be found.")

    tracked_companies = []
    seen_domains = set()
    tracked_pages = [
        line.strip()
        for line in tracked_pages_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    for tracked_page in tracked_pages:
        page_url = tracked_page
        if not page_url.startswith(("http://", "https://")):
            page_url = "https://" + page_url

        domain = urlparse(page_url).netloc.removeprefix("www.")
        if not domain or domain in seen_domains:
            continue

        seen_domains.add(domain)
        tracked_companies.append(
            {
                "name": company_name_from_url(page_url),
                "domain": domain,
                "homepage": f"https://{domain}",
            }
        )

    return tracked_companies


def clean_title(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def company_news_file(company_name, news_folder=NEWS_FOLDER):
    safe_name = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
    return Path(news_folder) / safe_name / "articles.json"


def company_rejected_file(company_name, news_folder=NEWS_FOLDER):
    safe_name = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
    return Path(news_folder) / safe_name / "rejected.json"


def company_needs_review_file(company_name, news_folder=NEWS_FOLDER):
    safe_name = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
    return Path(news_folder) / safe_name / "needs_review.json"


def load_article_list(article_file, error_message):
    if not article_file.exists():
        return []

    try:
        articles = json.loads(article_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise NewsMonitorError(error_message) from error

    if not isinstance(articles, list):
        raise NewsMonitorError(error_message)

    return articles


def load_saved_articles(company_name, news_folder=NEWS_FOLDER):
    news_file = company_news_file(company_name, news_folder)
    return load_article_list(
        news_file,
        "The saved news history could not be read.",
    )


def load_rejected_articles(company_name, news_folder=NEWS_FOLDER):
    rejected_file = company_rejected_file(company_name, news_folder)
    return load_article_list(
        rejected_file,
        "The rejected-news history could not be read.",
    )


def load_needs_review_articles(company_name, news_folder=NEWS_FOLDER):
    needs_review_file = company_needs_review_file(company_name, news_folder)
    return load_article_list(
        needs_review_file,
        "The news review queue could not be read.",
    )


def filter_unseen_articles(company_name, articles, news_folder=NEWS_FOLDER):
    saved_articles = load_saved_articles(company_name, news_folder)
    rejected_articles = load_rejected_articles(company_name, news_folder)
    needs_review_articles = load_needs_review_articles(company_name, news_folder)
    reviewed_articles = saved_articles + rejected_articles + needs_review_articles
    seen_urls = {article.get("url") for article in reviewed_articles}
    seen_titles = {
        clean_title(article.get("title", "")) for article in reviewed_articles
    }

    return [
        article
        for article in articles
        if article["url"] not in seen_urls
        and clean_title(article["title"]) not in seen_titles
    ]


def title_mentions_company(company_name, title):
    company_words = clean_title(company_name)
    title_words = clean_title(title)
    if not company_words or not title_words:
        return False
    return re.search(rf"(?:^| ){re.escape(company_words)}(?: |$)", title_words) is not None


def article_mentions_company(company, article):
    domain = company["domain"].lower()
    source = article.get("source", "").lower()
    url = article.get("url", "").lower()
    searchable_text = " ".join(
        [
            article.get("title", ""),
            article.get("description", ""),
        ]
    )
    return (
        title_mentions_company(company["name"], searchable_text)
        or domain in source
        or domain in url
    )


def prefilter_articles(company, articles):
    candidates = []
    needs_review = []

    for article in articles:
        likely_match = article_mentions_company(company, article)

        if likely_match:
            candidates.append(article)
            continue

        needs_review.append(article)

    return candidates, needs_review


def analyze_relevant_articles(company_name, articles):
    relevant_articles = []
    rejected_articles = []
    retry_articles = []

    for article in articles:
        print(f"Analyzing: {article['title']}")
        try:
            analysis = analyze_news_article(company_name, article)
        except NewsAnalysisError:
            print("Local AI analysis was unavailable. This article will be retried.")
            retry_articles.append(article)
            continue

        if not analysis["relevant"]:
            print("Ignored because it is not about the tracked company.")
            rejected_articles.append(
                {
                    **article,
                    "ai_analysis": analysis,
                }
            )
            continue

        relevant_articles.append(
            {
                **article,
                "ai_analysis": analysis,
            }
        )

    return relevant_articles, rejected_articles, retry_articles


def deduplicate_article_list(articles):
    unique_articles = []
    seen_urls = set()
    seen_titles = set()

    for article in articles:
        url = article.get("url")
        title = clean_title(article.get("title", ""))
        if not url or not title or url in seen_urls or title in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(title)
        unique_articles.append(article)

    return unique_articles


def save_needs_review_articles(company_name, articles, news_folder=NEWS_FOLDER):
    needs_review_file = company_needs_review_file(company_name, news_folder)
    queued_articles = deduplicate_article_list(articles)

    if queued_articles or needs_review_file.exists():
        needs_review_file.parent.mkdir(parents=True, exist_ok=True)
        needs_review_file.write_text(
            json.dumps(queued_articles, indent=2),
            encoding="utf-8",
        )

    return queued_articles


def save_rejected_articles(company_name, articles, news_folder=NEWS_FOLDER):
    if not articles:
        return []

    saved_rejections = load_rejected_articles(company_name, news_folder)
    seen_urls = {article.get("url") for article in saved_rejections}
    seen_titles = {
        clean_title(article.get("title", "")) for article in saved_rejections
    }
    new_rejections = []
    reviewed_at = datetime.now().isoformat(timespec="seconds")

    for article in articles:
        normalized_title = clean_title(article["title"])
        if article["url"] in seen_urls or normalized_title in seen_titles:
            continue

        new_rejections.append(
            {
                **article,
                "company": company_name,
                "reviewed_at": reviewed_at,
            }
        )
        seen_urls.add(article["url"])
        seen_titles.add(normalized_title)

    if new_rejections:
        rejected_file = company_rejected_file(company_name, news_folder)
        rejected_file.parent.mkdir(parents=True, exist_ok=True)
        rejected_file.write_text(
            json.dumps(new_rejections + saved_rejections, indent=2),
            encoding="utf-8",
        )

    return new_rejections


def save_new_articles(company_name, articles, news_folder=NEWS_FOLDER):
    saved_articles = load_saved_articles(company_name, news_folder)
    seen_urls = {article.get("url") for article in saved_articles}
    seen_titles = {
        clean_title(article.get("title", "")) for article in saved_articles
    }
    new_articles = []
    discovered_at = datetime.now().isoformat(timespec="seconds")

    for article in articles:
        normalized_title = clean_title(article["title"])
        if article["url"] in seen_urls or normalized_title in seen_titles:
            continue

        saved_article = {
            **article,
            "company": company_name,
            "discovered_at": discovered_at,
        }
        new_articles.append(saved_article)
        seen_urls.add(article["url"])
        seen_titles.add(normalized_title)

    if new_articles:
        news_file = company_news_file(company_name, news_folder)
        news_file.parent.mkdir(parents=True, exist_ok=True)
        news_file.write_text(
            json.dumps(new_articles + saved_articles, indent=2),
            encoding="utf-8",
        )

    return new_articles


def remove_duplicate_articles(articles):
    unique_articles = []
    seen_urls = set()
    seen_titles = set()

    for article in articles:
        url = article.get("url")
        title = article.get("title")
        if not url or not title:
            continue

        normalized_title = clean_title(title)
        if url in seen_urls or normalized_title in seen_titles:
            continue

        seen_urls.add(url)
        seen_titles.add(normalized_title)
        unique_articles.append(
            {
                "title": title.strip(),
                "url": url,
                "source": article.get("domain", "Unknown source"),
                "published_at": article.get("seendate", "Unknown time"),
                "language": article.get("language", "Unknown"),
                "source_country": article.get("sourcecountry", "Unknown"),
                "provider": article.get("provider", "GDELT"),
                "description": article.get("description", ""),
            }
        )

    return unique_articles


def search_gdelt_news(company_name, days=7, article_limit=25):
    try:
        response = requests.get(
            GDELT_SEARCH_URL,
            params={
                "query": f'"{company_name}" software',
                "mode": "artlist",
                "format": "json",
                "sort": "datedesc",
                "timespan": f"{days}d",
                "maxrecords": article_limit,
            },
            headers={
                "User-Agent": "CompetitorMonitor/0.1 (private local competitor monitor)"
            },
            timeout=30,
        )
    except requests.RequestException as error:
        raise NewsMonitorError("The news service could not be reached.") from error

    if response.status_code == 429:
        raise NewsMonitorError("The news service asked the monitor to try again later.")

    try:
        response.raise_for_status()
        articles = response.json().get("articles", [])
    except (requests.RequestException, ValueError) as error:
        raise NewsMonitorError("The news service returned an invalid response.") from error

    return remove_duplicate_articles(articles)


def search_google_news(company_name, domain, days=7, article_limit=25):
    try:
        response = requests.get(
            GOOGLE_NEWS_RSS_URL,
            params={
                "q": f'"{domain}" when:{days}d',
                "hl": "en-US",
                "gl": "US",
                "ceid": "US:en",
            },
            headers={
                "User-Agent": "CompetitorMonitor/0.1 (private local competitor monitor)"
            },
            timeout=30,
        )
        response.raise_for_status()
        feed = ElementTree.fromstring(response.content)
    except (requests.RequestException, ElementTree.ParseError) as error:
        raise NewsMonitorError("The backup news feed could not be reached.") from error

    articles = []
    for item in feed.findall("./channel/item")[:article_limit]:
        title = item.findtext("title")
        url = item.findtext("link")
        source = item.findtext("source") or "Google News"
        description_html = item.findtext("description") or ""
        published_text = item.findtext("pubDate") or ""

        if not title or not url:
            continue

        try:
            published_at = parsedate_to_datetime(published_text).isoformat()
        except (TypeError, ValueError):
            published_at = published_text or "Unknown time"

        source_suffix = f" - {source}"
        if title.endswith(source_suffix):
            title = title.removesuffix(source_suffix)

        description = re.sub(r"<[^>]+>", " ", unescape(description_html))
        description = re.sub(r"\s+", " ", description).strip()
        if description.startswith(title):
            description = description.removeprefix(title).strip()
        if description.endswith(source):
            description = description.removesuffix(source).strip()

        articles.append(
            {
                "title": title,
                "url": url,
                "domain": source,
                "seendate": published_at,
                "language": "English",
                "sourcecountry": "Unknown",
                "provider": "Google News RSS",
                "description": description,
            }
        )

    return remove_duplicate_articles(articles)


def search_company_news(company_name, domain=None, days=7, article_limit=25):
    try:
        return search_gdelt_news(company_name, days, article_limit)
    except NewsMonitorError as gdelt_error:
        if not domain:
            raise gdelt_error

    return search_google_news(company_name, domain, days, article_limit)


def main():
    try:
        tracked_companies = load_tracked_companies()
    except NewsMonitorError as error:
        print(error)
        raise SystemExit(1)

    if not tracked_companies:
        print("Add at least one company homepage to tracked_pages.txt.")
        raise SystemExit(1)

    for company in tracked_companies:
        print(f"Checking recent news for {company['name']}...")
        try:
            articles = search_company_news(company["name"], company["domain"])
            unseen_articles = filter_unseen_articles(company["name"], articles)
            candidate_articles, uncertain_articles = prefilter_articles(
                company, unseen_articles
            )
            existing_queue = load_needs_review_articles(company["name"])
            review_queue = deduplicate_article_list(
                existing_queue + uncertain_articles
            )
            review_batch = review_queue[:3]
            remaining_queue = review_queue[3:]

            if review_batch:
                print(
                    f"Reviewing {len(review_batch)} uncertain article(s) with Qwen."
                )
            if remaining_queue:
                print(
                    f"Deferred {len(remaining_queue)} uncertain article(s) "
                    "for later runs."
                )

            relevant_articles, rejected_articles, retry_articles = (
                analyze_relevant_articles(
                    company["name"], candidate_articles + review_batch
                )
            )
            new_articles = save_new_articles(company["name"], relevant_articles)
            save_rejected_articles(company["name"], rejected_articles)
            save_needs_review_articles(
                company["name"], remaining_queue + retry_articles
            )
        except NewsMonitorError as error:
            print(f"News check unavailable for {company['name']}: {error}\n")
            continue

        if new_articles:
            print(f"Saved {len(new_articles)} new article(s) for {company['name']}.\n")
        else:
            print(f"No new articles found for {company['name']}.\n")


if __name__ == "__main__":
    main()
