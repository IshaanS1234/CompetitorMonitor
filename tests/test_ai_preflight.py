from contextlib import redirect_stdout
from io import StringIO

import requests

from run_monitor import check_local_ai


class FakeResponse:
    def __init__(self, models):
        self.models = models

    def raise_for_status(self):
        return None

    def json(self):
        return {"models": self.models}


def ready_request(*args, **kwargs):
    return FakeResponse([{"name": "qwen3:8b"}])


def unavailable_request(*args, **kwargs):
    raise requests.ConnectionError("Ollama is unavailable")


output = StringIO()
with redirect_stdout(output):
    assert check_local_ai(ready_request) is True
assert "Local AI ready" in output.getvalue()

output = StringIO()
with redirect_stdout(output):
    assert check_local_ai(unavailable_request) is False
assert "monitor will continue" in output.getvalue()

print("Test passed: the monitor clearly reports local AI readiness.")
