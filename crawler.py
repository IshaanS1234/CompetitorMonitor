import difflib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ai_analyzer import AIAnalysisError, analyze_change
from page_discovery import cached_discovered_pages


TRACKED_PAGES_FILE = Path("tracked_pages.txt")
PAGE_WORKERS = 4
SNAPSHOTS_TO_KEEP = 10
AI_ANALYSIS_LOCK = Lock()


def expand_tracked_pages(tracked_pages):
    expanded_pages = []
    seen_pages = set()

    for tracked_page in tracked_pages:
        page_url = tracked_page
        if not page_url.startswith(("http://", "https://")):
            page_url = "https://" + page_url

        parsed_page = urlparse(page_url)
        is_homepage = parsed_page.path in ("", "/")
        pages_to_add = [page_url]

        if is_homepage:
            try:
                pages_to_add, discovery_source = cached_discovered_pages(page_url)
                if discovery_source == "cache":
                    print(
                        f"Using {len(pages_to_add)} cached page(s) "
                        f"for {page_url}.\n"
                    )
                elif discovery_source == "stale_cache":
                    print(
                        "Page rediscovery was unavailable. "
                        f"Using {len(pages_to_add)} older cached page(s) "
                        f"for {page_url}.\n"
                    )
                else:
                    print(f"Discovered useful pages from {page_url}...")
                    print(f"Found {len(pages_to_add)} page(s) to monitor.\n")
            except requests.RequestException:
                print(
                    "Page discovery was unavailable. "
                    "The homepage will still be monitored.\n"
                )

        for discovered_page in pages_to_add:
            normalized_page = discovered_page.rstrip("/")
            if normalized_page not in seen_pages:
                seen_pages.add(normalized_page)
                expanded_pages.append(discovered_page)

    return expanded_pages


def check_page(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed_url = urlparse(url)
    website_name = parsed_url.netloc.removeprefix("www.")
    page_name = parsed_url.path.strip("/").replace("/", "_") or "homepage"
    page_label = f"{website_name}/{page_name}"
    category_by_page = {
        "homepage": "Positioning",
        "pricing": "Pricing",
        "changelog": "Product",
    }
    category = category_by_page.get(page_name, "Other")
    print(f"Checking {url}...")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        page = BeautifulSoup(response.text, "html.parser")

        for unwanted_section in page(
            ["script", "style", "noscript", "svg", "nav", "footer"]
        ):
            unwanted_section.decompose()

        text = page.get_text(separator="\n", strip=True)

        page_folder = Path("snapshots") / website_name / page_name
        page_folder.mkdir(parents=True, exist_ok=True)
        checked_at = datetime.now()

        previous_snapshots = sorted(page_folder.glob("snapshot_*.txt"))

        if previous_snapshots:
            previous_contents = previous_snapshots[-1].read_text(encoding="utf-8")
            previous_text = previous_contents.split("\n\n", 1)[-1].strip()

            if text == previous_text:
                print(f"No changes detected on {page_label}.")
            else:
                print(f"Change detected on {page_label}:\n")

                comparison = difflib.ndiff(
                    previous_text.splitlines(), text.splitlines()
                )
                comparison_lines = list(comparison)
                removed_lines = [
                    line[2:] for line in comparison_lines if line.startswith("- ")
                ]
                added_lines = [
                    line[2:] for line in comparison_lines if line.startswith("+ ")
                ]

                report_lines = ["REMOVED"]
                report_lines.extend(f"- {line}" for line in removed_lines)
                report_lines.extend(["", "ADDED"])
                report_lines.extend(f"+ {line}" for line in added_lines)
                report_text = "\n".join(report_lines)

                print(report_text)

                changes_folder = Path("changes") / website_name / page_name
                changes_folder.mkdir(parents=True, exist_ok=True)
                change_filename = checked_at.strftime(
                    "change_%Y-%m-%d_%H-%M-%S.txt"
                )
                change_path = changes_folder / change_filename
                change_contents = (
                    f"Source: {url}\n"
                    f"Detected: {checked_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"{report_text}\n"
                )
                change_path.write_text(change_contents, encoding="utf-8")
                print(f"Saved change report: {change_path}")

                event = {
                    "company": website_name,
                    "page": page_name,
                    "category": category,
                    "detected_at": checked_at.isoformat(timespec="seconds"),
                    "source_url": url,
                    "summary": f"Changes detected on the {page_name} page.",
                    "removed": removed_lines,
                    "added": added_lines,
                    "change_report": str(change_path),
                }

                print("Analyzing the change with AI...")
                try:
                    with AI_ANALYSIS_LOCK:
                        event["ai_analysis"] = analyze_change(event)
                    analysis = event["ai_analysis"]
                    print("\nAI ANALYSIS")
                    print(f"Summary: {analysis['summary']}")
                    print(f"Category: {analysis['category']}")
                    print(f"Importance: {analysis['importance']}")
                    print(f"Why it matters: {analysis['why_it_matters']}")
                    print(f"Confidence: {analysis['confidence']}\n")
                except AIAnalysisError:
                    event["ai_analysis"] = None
                    print(
                        "AI analysis was unavailable. The factual change will still be saved."
                    )

                events_folder = Path("events") / website_name / page_name
                events_folder.mkdir(parents=True, exist_ok=True)
                event_filename = checked_at.strftime(
                    "event_%Y-%m-%d_%H-%M-%S.json"
                )
                event_path = events_folder / event_filename
                event_path.write_text(
                    json.dumps(event, indent=2), encoding="utf-8"
                )
                print(f"Saved structured event: {event_path}")
        else:
            print(f"Created the first snapshot for {page_label}.")

        filename = checked_at.strftime("snapshot_%Y-%m-%d_%H-%M-%S.txt")
        snapshot_path = page_folder / filename

        snapshot_contents = (
            f"Source: {url}\n"
            f"Checked: {checked_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"{text}\n"
        )
        snapshot_path.write_text(snapshot_contents, encoding="utf-8")

        print(f"Saved snapshot: {snapshot_path}\n")
        removed_snapshot_count = prune_old_snapshots(page_folder)
        if removed_snapshot_count:
            print(
                f"Removed {removed_snapshot_count} older snapshot(s) "
                f"from {page_label}.\n"
            )
    except requests.RequestException:
        print(f"Could not reach {url}. Check the address and try again.\n")


def prune_old_snapshots(page_folder, snapshots_to_keep=SNAPSHOTS_TO_KEEP):
    if snapshots_to_keep < 1:
        raise ValueError("At least one snapshot must be kept.")

    snapshot_files = sorted(Path(page_folder).glob("snapshot_*.txt"))
    snapshots_to_remove = snapshot_files[:-snapshots_to_keep]

    for snapshot_path in snapshots_to_remove:
        snapshot_path.unlink()

    return len(snapshots_to_remove)


def check_pages(pages, worker_count=PAGE_WORKERS):
    if not pages:
        return

    safe_worker_count = min(worker_count, len(pages))
    with ThreadPoolExecutor(max_workers=safe_worker_count) as executor:
        list(executor.map(check_page, pages))


def main():
    if not TRACKED_PAGES_FILE.exists():
        print("The tracked_pages.txt file could not be found.")
        raise SystemExit

    tracked_pages = [
        line.strip()
        for line in TRACKED_PAGES_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if not tracked_pages:
        print("Add at least one webpage to tracked_pages.txt.")
        raise SystemExit

    pages_to_monitor = expand_tracked_pages(tracked_pages)

    print(
        f"Checking {len(pages_to_monitor)} page(s) with up to "
        f"{PAGE_WORKERS} simultaneous downloads.\n"
    )
    check_pages(pages_to_monitor)


if __name__ == "__main__":
    main()
