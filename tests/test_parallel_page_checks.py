import threading
import time
from unittest.mock import patch

from crawler import check_pages


active_workers = 0
highest_active_workers = 0
worker_lock = threading.Lock()


def fake_check_page(_url):
    global active_workers, highest_active_workers
    with worker_lock:
        active_workers += 1
        highest_active_workers = max(highest_active_workers, active_workers)

    time.sleep(0.05)

    with worker_lock:
        active_workers -= 1


with patch("crawler.check_page", side_effect=fake_check_page):
    check_pages([f"https://example.com/page-{number}" for number in range(8)])

assert highest_active_workers == 4
assert active_workers == 0

print("Test passed: page checks use no more than four simultaneous workers.")
