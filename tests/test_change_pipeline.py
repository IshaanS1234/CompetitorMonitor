import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import crawler


class FakeResponse:
    text = "<html><body><h1>Pro plan</h1><p>59 dollars</p></body></html>"

    def raise_for_status(self):
        pass


with tempfile.TemporaryDirectory() as temporary_folder:
    os.chdir(temporary_folder)

    page_folder = Path("snapshots/test-company.test/pricing")
    page_folder.mkdir(parents=True)
    previous_snapshot = page_folder / "snapshot_2026-09-11_12-00-00.txt"
    previous_snapshot.write_text(
        "Source: https://test-company.test/pricing\n"
        "Checked: 2026-09-11 12:00:00\n\n"
        "Pro plan\n"
        "49 dollars\n",
        encoding="utf-8",
    )

    fake_analysis = {
        "summary": "The Pro plan price increased.",
        "category": "Pricing",
        "importance": "High",
        "why_it_matters": "The change may affect competitive positioning.",
        "confidence": "High",
    }
    with (
        patch("crawler.requests.get", return_value=FakeResponse()),
        patch("crawler.analyze_change", return_value=fake_analysis),
    ):
        crawler.check_page("https://test-company.test/pricing")

    event_files = list(Path("events/test-company.test/pricing").glob("*.json"))
    assert len(event_files) == 1

    event = json.loads(event_files[0].read_text(encoding="utf-8"))
    assert event["removed"] == ["49 dollars"]
    assert event["added"] == ["59 dollars"]
    assert event["category"] == "Pricing"

    print("Test passed: snapshot, change report, and structured event were created.")
