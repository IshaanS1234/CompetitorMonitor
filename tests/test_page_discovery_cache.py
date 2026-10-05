import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests

from page_discovery import cached_discovered_pages


homepage = "https://example.com"
expected_pages = [homepage + "/", homepage + "/pricing"]

with tempfile.TemporaryDirectory() as temporary_folder:
    cache_file = Path(temporary_folder) / "page_cache.json"
    now = datetime.now(timezone.utc)

    with patch(
        "page_discovery.discover_pages",
        return_value=expected_pages,
    ) as discover_mock:
        first_pages, first_source = cached_discovered_pages(
            homepage,
            cache_file=cache_file,
            current_time=now,
        )
        second_pages, second_source = cached_discovered_pages(
            homepage,
            cache_file=cache_file,
            current_time=now + timedelta(days=1),
        )

    assert first_pages == expected_pages
    assert first_source == "discovered"
    assert second_pages == expected_pages
    assert second_source == "cache"
    assert discover_mock.call_count == 1

    with patch(
        "page_discovery.discover_pages",
        side_effect=requests.RequestException,
    ):
        stale_pages, stale_source = cached_discovered_pages(
            homepage,
            cache_file=cache_file,
            current_time=now + timedelta(days=8),
        )

    assert stale_pages == expected_pages
    assert stale_source == "stale_cache"

print("Test passed: discovery is cached and stale cache remains a safe fallback.")
