# 🩺 MediPlan AI v2 — Proactive MBBS Study Companion

> Adaptive, proactive, RAG-powered study planner for MBBS students.
> No modes to pick — the system detects your phase automatically.
> The AI initiates your study session at your exact scheduled time.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit Frontend                      │
│  main.py · Setup · Study Plan · Progress · Chat · Schedule│
│              talks to FastAPI via HTTP                    │
└────────────────────────┬────────────────────────────────┘
                         │ REST API
┌────────────────────────▼────────────────────────────────┐
│                  FastAPI Backend                          │
│  /profile  /plan  /chat  /progress  /proactive/trigger   │
│                                                           │
│  APScheduler (background)                                 │
│  ├── every 5 min: check user's schedule → fire proactive │
│  └── daily 7am: exam proximity check                     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                 LangGraph Agents                          │
│                                                           │
│  PlannerGraph:                                            │
│    RAG → PhaseDetect → [Planner | EmergencyPlanner]       │
│                ↑ conditional edge on phase                │
│                                                           │
│  ProactiveGraph:                                          │
│    Progress → DriftCheck → [Proactive | Replan | Skip]    │
│                ↑ conditional edges on drift + trigger     │
│                                                           │
│  TutorGraph:                                              │
│    Context → Tutor                                        │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              Shared Layer                                 │
│  SQLite (WAL mode — safe concurrent access)              │
│  Groq Llama 3.3-70B → Gemini 2.0 Flash fallback         │
│  CBME syllabus (11 subjects, 80+ topics)                 │
└─────────────────────────────────────────────────────────┘
```

## Phase auto-detection (no user-facing modes)

| Days to exam | Phase      | Behaviour                                      |
|---|---|---|
| > 60 days     | Marathon   | Deep coverage, spaced repetition, rest days    |
| 15–60 days    | Sprint     | High-yield first, daily practice questions     |
| 4–14 days     | Crunch     | Triage mode, high-yield only, 30-min sessions  |
| ≤ 3 days      | Emergency  | Revision of already-studied topics ONLY        |

## Proactive trigger types

| Trigger          | When                                           |
|---|---|
| `study_time`     | Exact minute of user's scheduled study window  |
| `behind_schedule`| Drift > 35% from expected completion          |
| `exam_near`      | 30, 14, 7, 3, 1 days before exam              |
| `streak_break`   | No activity for 2+ days                       |
| `replan_requested`| User clicked Replan button                  |

## Run locally

```bash
# 1. Install
pip install -r requirements.txt

# 2. Add API keys
cp .env.example .env
# edit .env with your GROQ_API_KEY

# 3. Start FastAPI backend (runs scheduler)
uvicorn backend.main:app --reload --port 8000

# 4. Start Streamlit (separate terminal)
cd frontend
streamlit run main.py
```

## Deploy

**Backend (FastAPI):** Railway / Render free tier
```
Start command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Frontend (Streamlit):** Streamlit Community Cloud
```
Entry point: frontend/main.py
Add GROQ_API_KEY and BACKEND_URL in Streamlit secrets
```

## LangGraph graphs

Three compiled StateGraphs with real conditional routing:

- `PlannerGraph` — `phase_node` → conditional edge → `planner_node` OR `emergency_planner_node`
- `ProactiveGraph` — `progress_node` → `drift_router` → `proactive_node` OR `replan_node` OR `skip_node`  
- `TutorGraph` — `context_node` → `tutor_node`

Built by Rajesh M | LangGraph · FastAPI · Groq · Streamlit · APScheduler · SQLite
