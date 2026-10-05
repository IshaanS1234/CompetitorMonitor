import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


PAGE_PRIORITIES = {
    "pricing": 1,
    "changelog": 2,
    "updates": 3,
    "product": 4,
    "products": 4,
    "features": 5,
    "solutions": 6,
    "customers": 7,
    "blog": 8,
    "careers": 9,
    "jobs": 9,
    "about": 10,
}

IGNORED_FILE_ENDINGS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".pdf",
    ".zip",
)
DISCOVERY_CACHE_FILE = Path("page_discovery_cache.json")
DISCOVERY_CACHE_DAYS = 7


def normalize_url(url):
    parsed_url = urlparse(url)
    clean_path = parsed_url.path.rstrip("/") or "/"
    return urlunparse(
        (parsed_url.scheme, parsed_url.netloc, clean_path, "", "", "")
    )


def discover_pages(homepage_url, page_limit=8):
    if not homepage_url.startswith(("http://", "https://")):
        homepage_url = "https://" + homepage_url

    homepage_url = normalize_url(homepage_url)
    homepage_domain = urlparse(homepage_url).netloc.removeprefix("www.")

    response = requests.get(homepage_url, timeout=10)
    response.raise_for_status()
    page = BeautifulSoup(response.text, "html.parser")
    candidates = {}

    for link in page.find_all("a", href=True):
        candidate_url = normalize_url(urljoin(homepage_url, link["href"]))
        parsed_candidate = urlparse(candidate_url)
        candidate_domain = parsed_candidate.netloc.removeprefix("www.")

        if parsed_candidate.scheme not in ("http", "https"):
            continue
        if candidate_domain != homepage_domain:
            continue
        if parsed_candidate.path.lower().endswith(IGNORED_FILE_ENDINGS):
            continue

        path_parts = [
            part for part in parsed_candidate.path.split("/") if part
        ]
        if len(path_parts) > 1:
            continue

        searchable_text = (
            f"{parsed_candidate.path} {link.get_text(' ', strip=True)}".lower()
        )
        matching_priorities = [
            priority
            for keyword, priority in PAGE_PRIORITIES.items()
            if keyword in searchable_text
        ]

        if matching_priorities:
            candidates[candidate_url] = min(matching_priorities)

    ordered_candidates = sorted(
        candidates,
        key=lambda candidate: (candidates[candidate], candidate),
    )
    discovered_pages = [homepage_url]

    for candidate in ordered_candidates:
        if candidate != homepage_url:
            discovered_pages.append(candidate)
        if len(discovered_pages) >= page_limit:
            break

    return discovered_pages


def load_discovery_cache(cache_file=DISCOVERY_CACHE_FILE):
    cache_file = Path(cache_file)
    if not cache_file.exists():
        return {}

    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    return cache if isinstance(cache, dict) else {}


def save_discovery_cache(cache, cache_file=DISCOVERY_CACHE_FILE):
    cache_file = Path(cache_file)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def cached_discovered_pages(
    homepage_url,
    page_limit=8,
    cache_file=DISCOVERY_CACHE_FILE,
    max_age_days=DISCOVERY_CACHE_DAYS,
    current_time=None,
):
    if not homepage_url.startswith(("http://", "https://")):
        homepage_url = "https://" + homepage_url

    cache_key = normalize_url(homepage_url)
    cache = load_discovery_cache(cache_file)
    cached_entry = cache.get(cache_key) or {}
    cached_pages = cached_entry.get("pages") or []
    discovered_at = cached_entry.get("discovered_at")
    now = current_time or datetime.now().astimezone()

    cache_is_fresh = False
    if cached_pages and discovered_at:
        try:
            cached_time = datetime.fromisoformat(discovered_at)
            if cached_time.tzinfo is None:
                cached_time = cached_time.astimezone()
            cache_is_fresh = now - cached_time < timedelta(days=max_age_days)
        except (TypeError, ValueError):
            cache_is_fresh = False

    if cache_is_fresh:
        return cached_pages[:page_limit], "cache"

    try:
        discovered_pages = discover_pages(homepage_url, page_limit)
    except requests.RequestException:
        if cached_pages:
            return cached_pages[:page_limit], "stale_cache"
        raise

    cache[cache_key] = {
        "pages": discovered_pages,
        "discovered_at": now.isoformat(timespec="seconds"),
    }
    save_discovery_cache(cache, cache_file)
    return discovered_pages, "discovered"
