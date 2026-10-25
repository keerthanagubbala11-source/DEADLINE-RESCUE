"""Daily plan generation.

The rule-based engine always works. Gemini (optional) only reorders tasks and
writes the reasons. Time blocks are always built by our own code, and the AI
response is validated because it is untrusted input.
"""
import json
import os
from datetime import datetime, timedelta

import requests

import engine

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


class PlanError(Exception):
    pass


def _api_key():
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None


def ai_available():
    return bool(_api_key())


def ask_gemini(candidates, available_hours):
    key = _api_key()
    if not key:
        raise PlanError("no API key configured")
    info = [
        {k: r[k] for k in ("id", "title", "category", "deadline", "days_left",
                           "importance", "remaining", "group", "score")}
        for r in candidates
    ]
    prompt = (
        "You are a study and productivity planner. Using ONLY the tasks below, "
        "order them for today and explain briefly. Do not invent tasks, deadlines "
        "or durations. Use only the given ids. Be supportive, not guilt-inducing.\n"
        f"Hours available today: {available_hours}\n"
        f"Tasks (JSON): {json.dumps(info)}\n"
        'Reply as JSON: {"summary": str, "order": [{"id": str, "reason": str}], '
        '"tips": [str]}'
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3},
    }
    try:
        resp = requests.post(
            GEMINI_URL.format(GEMINI_MODEL),
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json=body, timeout=30,
        )
        if resp.status_code == 429:
            raise PlanError("rate limit reached")
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
    except PlanError:
        raise
    except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
        raise PlanError(type(e).__name__) from e

    # Validate: keep only known ids, drop duplicates, coerce types.
    known = {r["id"] for r in candidates}
    order, reasons, seen = [], {}, set()
    for item in data.get("order", []):
        tid = item.get("id") if isinstance(item, dict) else None
        if tid in known and tid not in seen:
            seen.add(tid)
            order.append(tid)
            reasons[tid] = str(item.get("reason", ""))[:300]
    if not order:
        raise PlanError("AI returned no usable plan")
    for r in candidates:  # tasks the AI skipped keep their rule-based position
        if r["id"] not in seen:
            order.append(r["id"])
    tips = [str(x)[:200] for x in data.get("tips", []) if isinstance(x, str)][:4]
    return {"order": order, "reasons": reasons, "summary": str(data.get("summary", ""))[:500], "tips": tips}


def make_plan(rows, today, available_hours, start: datetime, block_min, break_min, use_ai):
    candidates = [r for r in rows if r["status"] not in ("Completed", "Blocked")]
    by_id = {r["id"]: r for r in candidates}
    reasons = {r["id"]: r["why"] for r in candidates}
    source, summary, tips, notice = "Rule-based plan", "", [], None

    if use_ai and candidates:
        try:
            ai = ask_gemini(candidates, available_hours)
            candidates = [by_id[i] for i in ai["order"]]
            reasons.update(ai["reasons"])
            summary, tips = ai["summary"], ai["tips"]
            source = "Gemini-assisted plan (validated)"
        except PlanError as e:
            notice = f"AI unavailable ({e}). Showing the rule-based plan instead."

    # Hard deadlines win: overdue tasks always come first, whatever the AI said.
    candidates = sorted(candidates, key=lambda r: 0 if r["group"] == "Overdue" else 1)

    budget = int(available_hours * 60)
    required = sum(engine.daily_share_minutes(r, today) for r in candidates)
    blocks, unscheduled = [], []
    cursor, used = start, 0
    for r in candidates:
        need = engine.daily_share_minutes(r, today)
        while need > 0 and used < budget:
            m = min(block_min, need, budget - used)
            end = cursor + timedelta(minutes=m)
            blocks.append({
                "task_id": r["id"], "task": r["title"], "group": r["group"],
                "start": cursor.strftime("%H:%M"), "end": end.strftime("%H:%M"),
                "minutes": m, "reason": reasons.get(r["id"], ""),
            })
            cursor = end + timedelta(minutes=break_min)
            used += m
            need -= m
        if need > 0:
            unscheduled.append({"task": r["title"], "group": r["group"], "minutes_short": need})

    warnings = []
    if required > budget:
        warnings.append(
            f"Overload: about {required / 60:.1f}h of work needs doing today but only "
            f"{available_hours:.1f}h is available. Not everything fits."
        )
    for r in candidates:
        if r["group"] in ("Overdue", "At Risk"):
            warnings.append(f"{r['title']}: {r['group'].lower()}. Consider talking to your teacher or asking for an extension.")
    if not summary:
        summary = f"{len(candidates)} active task(s); about {required / 60:.1f}h suggested today, {available_hours:.1f}h available."

    return {
        "source": source, "summary": summary, "tips": tips, "notice": notice,
        "blocks": blocks, "unscheduled": unscheduled, "warnings": warnings,
        "required_minutes": required, "available_minutes": budget,
        "overload": required > budget, "date": today.isoformat(),
    }
