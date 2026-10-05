import tempfile
from pathlib import Path

from crawler import prune_old_snapshots


with tempfile.TemporaryDirectory() as temporary_folder:
    page_folder = Path(temporary_folder)

    for number in range(1, 13):
        snapshot_path = page_folder / f"snapshot_2026-09-{number:02d}_12-00-00.txt"
        snapshot_path.write_text(f"snapshot {number}", encoding="utf-8")

    permanent_event = page_folder / "event_should_remain.json"
    permanent_event.write_text("{}", encoding="utf-8")

    removed_count = prune_old_snapshots(page_folder, snapshots_to_keep=10)
    remaining_snapshots = sorted(page_folder.glob("snapshot_*.txt"))

    assert removed_count == 2
    assert len(remaining_snapshots) == 10
    assert remaining_snapshots[0].name == "snapshot_2026-09-03_12-00-00.txt"
    assert remaining_snapshots[-1].name == "snapshot_2026-09-12_12-00-00.txt"
    assert permanent_event.exists()

print("Test passed: only the newest snapshots are kept.")
