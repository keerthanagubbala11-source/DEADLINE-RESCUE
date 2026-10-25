"""Transparent priority engine: plain Python, no AI involved.

score = 45 * urgency + 35 * importance + 20 * effort
  urgency    = 1.0 if due today/overdue, else 1 / (1 + days_left)
  importance = Low 0.25, Medium 0.5, High 0.75, Critical 1.0
  effort     = min(remaining_hours / 8, 1)
  +20 if overdue, +30 if the user pinned the task.

Groups (checked in this order):
  Completed -> Overdue -> At Risk -> Do First -> Schedule Soon -> Can Wait
  At Risk: remaining work cannot fit in (days_left + 1) days at the daily hour cap.
  Do First: score >= 60 or due within 1 day.
  Schedule Soon: due within 7 days.
"""
import math
from datetime import date

IMPORTANCE = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
GROUP_ORDER = ["Overdue", "At Risk", "Do First", "Schedule Soon", "Can Wait", "Completed"]


def remaining_hours(t):
    return max(float(t["est_hours"]) - float(t.get("spent_hours", 0.0)), 0.0)


def days_left(t, today: date):
    return (date.fromisoformat(t["deadline"]) - today).days


def score(t, today: date):
    d = days_left(t, today)
    urgency = 1.0 if d <= 0 else 1 / (1 + d)
    importance = IMPORTANCE[t["importance"]] / 4
    effort = min(remaining_hours(t) / 8, 1.0)
    s = 45 * urgency + 35 * importance + 20 * effort
    if d < 0:
        s += 20
    if t.get("pinned"):
        s += 30
    return round(s, 1)


def classify(t, today: date, daily_hours: float):
    if t["status"] == "Completed":
        return "Completed"
    d = days_left(t, today)
    if d < 0:
        return "Overdue"
    if remaining_hours(t) > (d + 1) * daily_hours:
        return "At Risk"
    if score(t, today) >= 60 or d <= 1:
        return "Do First"
    if d <= 7:
        return "Schedule Soon"
    return "Can Wait"


def explain(t, today: date):
    d = days_left(t, today)
    if d < 0:
        when = f"{-d} day(s) past its deadline"
    elif d == 0:
        when = "due today"
    elif d == 1:
        when = "due tomorrow"
    else:
        when = f"due in {d} days"
    parts = [when, f"{t['importance']} importance", f"{remaining_hours(t):.1f}h of work left"]
    if t.get("pinned"):
        parts.append("pinned by you")
    text = ", ".join(parts)
    return text[0].upper() + text[1:]


def daily_share_minutes(t, today: date):
    """Minutes to do today so the work is spread evenly up to the deadline."""
    rem = remaining_hours(t) * 60
    d = days_left(t, today)
    return math.ceil(rem) if d <= 0 else math.ceil(rem / (d + 1))


def analyse(tasks, today: date, daily_hours: float):
    """Return tasks enriched with score, group, days_left, remaining and a reason."""
    out = []
    for t in tasks:
        out.append({
            **t,
            "score": score(t, today),
            "group": classify(t, today, daily_hours),
            "days_left": days_left(t, today),
            "remaining": round(remaining_hours(t), 2),
            "why": explain(t, today),
        })
    return sorted(out, key=lambda r: -r["score"])
