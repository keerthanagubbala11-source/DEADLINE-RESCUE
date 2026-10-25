"""Tiny JSON-file storage, one folder per user. Fine for a demo; swap for a database later."""
import json
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).parent / "data"


def _user_dir(username):
    d = DATA / "users" / username  # username is validated by auth.py ([a-z0-9_] only)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_tasks(username):
    return _read(_user_dir(username) / "tasks.json", [])


def save_tasks(username, tasks):
    (_user_dir(username) / "tasks.json").write_text(json.dumps(tasks, indent=2))


def load_plan(username):
    return _read(_user_dir(username) / "plan.json", None)


def save_plan(username, plan):
    (_user_dir(username) / "plan.json").write_text(json.dumps(plan, indent=2))


def sample_tasks(today: date):
    def d(n):
        return (today + timedelta(days=n)).isoformat()

    rows = [
        ("Finish DBMS assignment", "Academic", d(1), 3, "High"),
        ("Prepare for data structures exam", "Academic", d(5), 10, "Critical"),
        ("Update resume", "Career", d(7), 2, "Medium"),
        ("Buy groceries", "Household", d(0), 1, "Low"),
        ("Practice 5 DSA problems", "Career", d(3), 2.5, "High"),
        ("Submit lab record", "Academic", d(-1), 1.5, "High"),
    ]
    return [
        {
            "id": f"sample-{i}", "title": t, "description": "", "category": c,
            "deadline": dl, "est_hours": h, "spent_hours": 0.0,
            "importance": imp, "status": "Not Started", "pinned": False,
            "created": today.isoformat(), "completed_on": None,
        }
        for i, (t, c, dl, h, imp) in enumerate(rows)
    ]
