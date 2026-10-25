# Deadline Rescue (Python / Streamlit)

AI-assisted workload planner: tasks, transparent priority scoring, daily plan, insights.

## Run locally
```
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Enable Gemini (optional)
Get a key at https://aistudio.google.com, then either
- copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste the key, or
- set the environment variable `GEMINI_API_KEY`.

Without a key the app uses the rule-based planner. The key is read only on the server side.

## Files
- `engine.py`  priority score and grouping (documented in the docstring)
- `planner.py` schedule builder, Gemini call, validation, rule-based fallback
- `auth.py`    signup/login with salted password hashes
- `storage.py` per-user JSON storage and sample data
- `app.py`     Streamlit interface
