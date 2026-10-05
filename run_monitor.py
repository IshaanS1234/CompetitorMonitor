import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests


PROJECT_FOLDER = Path(__file__).resolve().parent
REPORTS_FOLDER = PROJECT_FOLDER / "reports"
OLLAMA_MODELS_URL = "http://127.0.0.1:11434/api/tags"
LOCAL_AI_MODEL = "qwen3:8b"


def check_local_ai(request_get=requests.get):
    try:
        response = request_get(OLLAMA_MODELS_URL, timeout=3)
        response.raise_for_status()
        models = response.json().get("models", [])
    except (requests.RequestException, ValueError):
        print(
            "Warning: Ollama is not running. The monitor will continue, "
            "but new items cannot receive AI analysis."
        )
        return False

    installed_models = {
        model.get("name") or model.get("model")
        for model in models
        if isinstance(model, dict)
    }
    if LOCAL_AI_MODEL not in installed_models:
        print(
            f"Warning: {LOCAL_AI_MODEL} is not installed. The monitor will "
            "continue without AI analysis."
        )
        return False

    print(f"Local AI ready: {LOCAL_AI_MODEL}")
    return True


def main():
    started_at = datetime.now()
    check_local_ai()
    website_result = subprocess.run(
        [sys.executable, "crawler.py"],
        cwd=PROJECT_FOLDER,
        capture_output=True,
        text=True,
    )
    news_result = subprocess.run(
        [sys.executable, "news_monitor.py"],
        cwd=PROJECT_FOLDER,
        capture_output=True,
        text=True,
    )
    hacker_news_result = subprocess.run(
        [sys.executable, "hacker_news_monitor.py"],
        cwd=PROJECT_FOLDER,
        capture_output=True,
        text=True,
    )

    report = (
        "DAILY COMPETITOR MONITOR REPORT\n"
        f"Run: {started_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "WEBSITE MONITOR\n"
        f"{website_result.stdout}\n"
        "NEWS MONITOR\n"
        f"{news_result.stdout}\n"
        "HACKER NEWS MONITOR\n"
        f"{hacker_news_result.stdout}"
    )

    if website_result.stderr:
        report += f"\nWEBSITE ERROR DETAILS\n{website_result.stderr}"
    if news_result.stderr:
        report += f"\nNEWS ERROR DETAILS\n{news_result.stderr}"
    if hacker_news_result.stderr:
        report += f"\nHACKER NEWS ERROR DETAILS\n{hacker_news_result.stderr}"

    REPORTS_FOLDER.mkdir(exist_ok=True)
    report_name = started_at.strftime("report_%Y-%m-%d_%H-%M-%S.txt")
    report_path = REPORTS_FOLDER / report_name
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"Saved daily report: {report_path}")

    dashboard_result = subprocess.run(
        [sys.executable, "generate_dashboard_data.py"],
        cwd=PROJECT_FOLDER,
        capture_output=True,
        text=True,
    )
    if dashboard_result.returncode == 0:
        print("Updated private dashboard data.")
    else:
        print("The monitor finished, but the private dashboard could not be updated.")
        if dashboard_result.stderr:
            print(f"DASHBOARD ERROR DETAILS\n{dashboard_result.stderr}")

    if (
        website_result.returncode != 0
        or news_result.returncode != 0
        or hacker_news_result.returncode != 0
        or dashboard_result.returncode != 0
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
