import tempfile
from pathlib import Path

from news_monitor import (
    filter_unseen_articles,
    load_needs_review_articles,
    prefilter_articles,
    save_needs_review_articles,
)


shortcut = {"name": "Shortcut", "domain": "shortcut.com"}
articles = [
    {
        "title": "Shortcut launches a new planning feature",
        "url": "https://news.google.com/example-1",
        "source": "Example News",
        "provider": "Google News RSS",
    },
    {
        "title": "A new gaming controller is now available",
        "url": "https://news.google.com/example-2",
        "source": "Gaming News",
        "provider": "Google News RSS",
    },
    {
        "title": "A faster way to open an Android settings screen",
        "url": "https://example.com/android-shortcut",
        "source": "Mobile News",
        "provider": "GDELT",
    },
    {
        "title": "A project-management startup changes its roadmap",
        "description": "Shortcut announced the change this morning.",
        "url": "https://news.google.com/example-3",
        "source": "Example News",
        "provider": "Google News RSS",
    },
    {
        "title": "A product update from the Shortcut team",
        "url": "https://shortcut.com/blog/update",
        "source": "shortcut.com",
        "provider": "Google News RSS",
    },
]

candidates, filtered_out = prefilter_articles(shortcut, articles)

assert len(candidates) == 3
assert candidates[0]["title"] == "Shortcut launches a new planning feature"
assert candidates[1]["description"] == "Shortcut announced the change this morning."
assert candidates[2]["source"] == "shortcut.com"
assert len(filtered_out) == 2
assert filtered_out[0]["title"] == "A new gaming controller is now available"
assert filtered_out[1]["provider"] == "GDELT"

with tempfile.TemporaryDirectory() as temporary_folder:
    queue_folder = Path(temporary_folder)
    save_needs_review_articles("Shortcut", filtered_out, queue_folder)
    queued = load_needs_review_articles("Shortcut", queue_folder)
    assert len(queued) == 2

    unseen = filter_unseen_articles(
        "Shortcut",
        filtered_out
        + [
            {
                "title": "Another uncertain result",
                "url": "https://news.google.com/example-4",
            }
        ],
        queue_folder,
    )
    assert len(unseen) == 1
    assert unseen[0]["title"] == "Another uncertain result"

print("Test passed: uncertain results are separated without being discarded.")
