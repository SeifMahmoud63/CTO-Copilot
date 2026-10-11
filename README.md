<div align="center">

# 🛰️ CTO Watch — Engineering Leadership Hub
### *CTO-Copilot · Your AI Command Center for Team Velocity, PR Intelligence & Executive Insight*

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](./docker-compose.yml)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](./alembic/versions/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](./docker-compose.yml)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-7C3AED?style=for-the-badge)](./app/services/chat_service.py)
[![Bedrock](https://img.shields.io/badge/Bedrock-Qwen_3_32B-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)](./app/services/llm_service.py)
[![Groq](https://img.shields.io/badge/Groq-Fallback-F55036?style=for-the-badge)](./app/services/llm_service.py)
[![Deepgram](https://img.shields.io/badge/Deepgram-Voice_Agent-13EF93?style=for-the-badge)](./app/services/voice_service.py)
[![Celery](https://img.shields.io/badge/Celery-Beat_08:00-37814A?style=for-the-badge)](./app/services/celery_app.py)

**One dashboard to rule all PRs. AI summaries in seconds. Impact-ranked engineers. A chatbot that *queries your live database*. A voice agent you can talk to. Daily PDF reports on your desk at 08:00. All behind a password + Google Authenticator gate.**

[🚀 Quick Start](#-quick-start--run-in-60-seconds) · [✨ Features](#-feature-atlas--every-screen-dissected) · [🏗️ Architecture](#️-system-architecture) · [🤖 AI Stack](#-ai-brain--bedrock--groq--jev) · [📡 API](#-api-reference) · [⚙️ Config](#️-configuration--env-cheat-sheet)

</div>

---

> **🔒 Privacy note on screenshots:** all screenshots below are **sanitized mock placements** — real PR titles, usernames, avatars and repo names are blurred / replaced with placeholders. Drop your own captures into `docs/screenshots/` and they render automatically. No sensitive data from the live site is exposed in this file.

## 📸 Product Tour (Screenshots)

> Put PNG captures here — the README already points at them. Recommended size 1600×900, blur titles/avatars before committing.
>
> ```
> docs/screenshots/01-home.png
> docs/screenshots/02-pr-requests.png
> docs/screenshots/03-overdue.png
> docs/screenshots/04-dashboard.png
> docs/screenshots/05-chatbot.png
> docs/screenshots/06-reports.png
> docs/screenshots/07-voice.png
> docs/screenshots/08-login.png
> ```

| Screen | Preview | What you're looking at |
|---|---|---|
| 🏠 **Home — Team Velocity & Pulse** | <img src="docs/screenshots/01-home.png" alt="Home view — SLA health card and weekly activity chart" width="800"> | Live SLA Health card (% within SLA + bar) + 7-day Opened-vs-Merged SVG chart |
| 🔀 **PR Requests Directory** | <img src="docs/screenshots/02-pr-requests.png" alt="PR Requests table with AI summaries and scores" width="800"> | Auto-populated PR table: author · date · executive AI summary · state · impact score · details link + `All/Open/Merged/Closed` filters |
| ⚠️ **Overdue / SLA Alerts** | <img src="docs/screenshots/03-overdue.png" alt="Overdue PRs table with SLA countdown" width="800"> | Every open PR older than `PR_STALE_THRESHOLD_DAYS` (default **5**) with overdue-duration counter |
| 🏆 **Engineer Impact Dashboard** | <img src="docs/screenshots/04-dashboard.png" alt="Leaderboard ranked by impact" width="800"> | Leaderboard ranked by **impact, not commit count** — 8 time windows (Today → 1 Year), avg/total impact, tier badges |
| 💬 **CTO AI Copilot (Chat)** | <img src="docs/screenshots/05-chatbot.png" alt="Chat sessions sidebar and messages" width="800"> | LangGraph agent with live read-only MySQL access, sessions sidebar, bilingual AR/EN, query-rewrite for follow-ups |
| 📄 **Daily CTO Reports** | <img src="docs/screenshots/06-reports.png" alt="Daily reports table with preview and download" width="800"> | One PDF every morning at **08:00 Africa/Cairo** — Preview inline / Download attachment |
| 🎙️ **Voice Copilot** | <img src="docs/screenshots/07-voice.png" alt="Voice orb visualizer with transcript" width="800"> | Push-to-talk Deepgram agent: glowing orb · live transcript · real-time `🔍 Querying MySQL:` badge |
| 🔐 **Access Gate** | <img src="docs/screenshots/08-login.png" alt="Password plus TOTP login" width="800"> | Shared password → QR enroll in Google Authenticator → 6-digit TOTP → optional *Remember this device* |

---

## 📚 Table of Contents

- [🌐 Where everything lives](#-where-everything-lives)
- [✨ Feature Atlas — every screen dissected](#-feature-atlas--every-screen-dissected)
  - [1 · Home](#1--home--team-velocity--engineering-pulse)
  - [2 · PR Requests](#2--pr-requests--automated-pr-intelligence)
  - [3 · Overdue](#3--overdue--sla-radar)
  - [4 · Dashboard](#4--dashboard--engineer-impact--leaderboard)
  - [5 · Chatbot](#5--chatbot--cto-ai-copilot-langgraph-agent)
  - [6 · Daily Reports](#6--daily-cto-reports--08h00-executive-brief)
  - [7 · Voice Agent](#7--voice-agent--deepgram-live-copilot)
  - [8 · Access Gate](#8--access-gate--password--totp)
- [🏗️ System Architecture](#️-system-architecture)
- [🧠 AI Brain — Bedrock + Groq + JEV](#-ai-brain--bedrock--groq--jev)
- [🗄️ Data Model](#️-data-model--mysql--alembic)
- [📡 API Reference](#-api-reference)
- [⚙️ Configuration — .env cheat sheet](#️-configuration--env-cheat-sheet)
- [🚀 Quick Start — run in 60 seconds](#-quick-start--run-in-60-seconds)
- [🗂️ Project Structure](#️-project-structure)
- [🧪 Testing](#-testing)
- [🛡️ Security & Guardrails](#️-security--guardrails)
- [🗺️ Roadmap](#️-roadmap)
- [🤝 Contributing](#-contributing)

---

## 🌐 Where Everything Lives

| Entry point | URL | What it is |
|---|---|---|
| 🖥️ **Web App** | `http://localhost:8000/` | CTO Watch SPA (Home · PRs · Overdue · Dashboard · Chat · Reports · Voice) |
| 📖 **Swagger Docs** | `http://localhost:8000/docs` | Interactive OpenAPI explorer (try every endpoint) |
| 💚 **Health** | `http://localhost:8000/api/health` | Status + repo + active LLM provider (Bedrock vs Groq) |
| 🔀 **PRs API** | `http://localhost:8000/api/prs` | Raw PR intelligence JSON |
| 🔑 **Login** | `http://localhost:8000/login` | Password + TOTP gate |

---

## ✨ Feature Atlas — Every Screen Dissected

### 1 · 🏠 Home — Team Velocity & Engineering Pulse

**The 10-second executive glance.** No tables, no noise — just *are we healthy?* Every number is computed live from `GET /api/prs` — no static figures.

```
┌─────────────────────────────────────────────────────────────┐
│  [CTO Executive Overview]                                    │
│  Team Velocity & Engineering Pulse                           │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ SLA Health                              [Healthy]      │ │
│  │ 92%  ████████████████████░░░░                          │ │
│  │ 11 within SLA · 1 breached of 12 open                  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  Weekly PR Activity — last 7 days   (● Opened  ● Merged)    │
│   3 ┤        ╭─╮                                            │
│   2 ┤   ╭────╯ ╰╮      ╭╮                                   │
│   1 ┤───╯ green ╰──────╯╰──                                │
│   0 ┼───┴───┴───┴───┴───┴───┴───                           │
│     Mon 5  Tue 6 …                         9 opened · 6 merged│
└─────────────────────────────────────────────────────────────┘
```

- **SLA Health card** — share of currently-open PRs still inside the SLA window (`within / open × 100`). Chip states: `All Clear` (nothing open) · `Healthy ≥90%` · `Watch 70–89%` · `At Risk <70%`, with a color-coded progress bar (green/amber/red).
- **Weekly PR Activity chart** — dependency-free SVG line chart over the last 7 local days: **Opened** (blue, by `created_at`) vs **Merged** (green, by `state + updated_at`), integer gridlines, day labels, totals footer. Empty state when a quiet week happens.
- **Refresh:** loads on first paint + every Home navigation + the global 25s background poll (`loadHome()` in `web/app.js`).
- **Navigation hub** — top bar (`Home` shortcut · `Team Online` presence · `Workspace Menu` drawer) + right slide-out drawer with live count pills (`PRs: N` · `Overdue: M`).
- Files: `web/index.html` (homeView) · `web/app.js` (`loadHome/renderSLA/renderWeeklyChart`) · `web/style.css` (`.sla-bar`, `.chart-card`, `.chart-line…`)

---

### 2 · 🔀 PR Requests — Automated PR Intelligence

**Every GitHub PR, auto-fetched, auto-summarized, auto-scored. Zero manual work.**

```
  GitHub ──poll every 30s──▶ FastAPI ──diff (3500 chars)──▶ Bedrock Qwen
     │                          │                                │ fail?
     │                     webhook (opened /                    ▼
     │                     synchronize / reopened)         Groq fallback
     │                          │                                │
     └──────────────────────────┴──── summary + JEV score ──────┘
                                        │ MySQL upsert + cache
                                        ▼
                              ┌──────────────────┐
                              │ # │ Author │ Date │
                              │ Summary │ State  │
                              │ Score │ Details  │
                              └──────────────────┘
```

- **Filter bar:** `All · Open · Merged · Closed` — instant client-side filtering.
- **Columns:** `#` · `ID` · `Author` (avatar + login) · `Created` · **AI Summary (2–3 dense sentences)** · `State` badge · **Impact Score (1–10)** · `PR Details` (GitHub link).
- **Refresh PRs button** re-syncs from GitHub on demand; background task `auto_poll_prs()` (`app/main.py`) polls continuously; webhook `POST /api/webhook/github` re-summarizes on `opened/synchronize/reopened`.
- **Summary quality rules** (`app/core/enums.py::SystemPrompt`): concrete mechanism over generic filler, diff-grounded, flags description↔diff mismatches, admits truncation, never follows instructions hidden inside the PR.
- Empty state: *"No PRs Detected Yet — will populate with AI summaries once submitted on GitHub."*
- Backend: `app/services/github_service.py::get_pull_requests` · `summarize_pr` · `fetch_pr_diff` → `app/services/llm_service.py` → `app/services/jev_service.py` → `app/services/db_service.py::save_or_update_pr`

<details>
<summary><b>🔬 How one PR gets its brain — step by step</b></summary>

1. List API `GET /repos/{repo}/pulls` → raw JSON (id, number, title, user, branches, timestamps, `merged_at`).
2. State resolved: `merged_at ? merged : open/closed` (`PRStatus` enum).
3. Diff fetched with `Accept: application/vnd.github.v3.diff`, truncated at **3500 chars** (flag `is_truncated` passed to the prompt).
4. Prompt assembled from `UserPromptTemplate.PR_DIFF_TEMPLATE` (metadata + description + diff excerpt).
5. `LLMService.generate_pr_summary()` → Bedrock Qwen primary, Groq fallback via circuit breaker.
6. `JevService.evaluate_impact(summary)` → score **1.0–10.0** (TypeSafe `jev-latest`, 10-level criteria from *typo* → *platform upgrade*).
7. Tier assigned: `≥8 Critical Driver · ≥6.5 High Impact · ≥5 Solid Contributor · else Routine Support`.
8. In-memory `summary_cache` + MySQL upsert (`pull_requests`) + `rebuild_engineers()` aggregates.

</details>

---

### 3 · ⚠️ Overdue — SLA Radar

**Catches silent rot.** Any open PR older than the SLA threshold gets flagged before it becomes a bottleneck.

- Threshold = `PR_STALE_THRESHOLD_DAYS` (default **5 days**, tunable in `.env`), surfaced in the subtitle and API (`stale_threshold_days`).
- Columns: `#` · `Author` · `PR Details` · `Summary` · `Created` · **Overdue Duration (days)**.
- Healthy empty state (green): *"No Overdue PRs — all active PRs are within the SLA window."*
- Logic: `app/services/github_service.py::_compute_pr_overdue()` — age = `now − created_at`, only for `state == open`.
- Feeds the **Daily Report's "newly overdue"** section and the **Dashboard's overdue list**.

---

### 4 · 🏆 Dashboard — Engineer Impact & Leaderboard

**Ranked by architectural impact, not commit count.** The fair leaderboard.

| Time window | Days | Label |
|---|---|---|
| Today | `1` | Daily standup lens |
| 7 Days / 14 Days | `7 / 14` | Sprint lens |
| **30 Days** (default) | `30` | Monthly review lens |
| 3 / 6 / 9 Months / 1 Year | `90 / 180 / 270 / 365` | Perf-review lens |

- **Top cards:** Total PRs in window · Active Contributors · Top Impact Contributor (#1 + score).
- **Leaderboard columns:** `Rank` · `Engineer` · `PRs Count` · `Avg Impact (1–10)` · `Total Impact Pts` · `Impact Tier` badge.
- **Sorting:** total impact points desc, then avg score desc; ranks assigned 1…N.
- **Tiers:**

| Tier | Avg score | Meaning |
|---|---|---|
| 🔴 `Critical Driver` | ≥ 8.0 | Architecture-shaping work |
| 🟠 `High Impact` | ≥ 6.5 | Major features / integrations |
| 🔵 `Solid Contributor` | ≥ 5.0 | Steady feature delivery |
| ⚪ `Routine Support` | < 5.0 | Small fixes, docs, chores |

- Endpoint: `GET /api/dashboard?days=30` → `DashboardLeaderboardResponse` (`app/schemas/pr_schema.py`).
- Backend: `app/services/github_service.py::get_team_dashboard()` (cutoff filter → group by author → stats → sort → rank).

---

### 5 · 💬 Chatbot — CTO AI Copilot (LangGraph Agent)

**Talk to your database.** Ask *"who's blocked?"*, *"summarize today's report"* (عربي أو English — بيرد بنفس لغتك).

```
 User ("مين التاني؟ / and its author?")
   │
   ▼
 ┌─ Query Rewriter ─────────────────────────────┐
 │ deterministic ordinal fast-path ("اه التانيه" │
 │ → concrete PR #N) + LLM rewrite w/ history   │
 └──────────────────────┬───────────────────────┘
                        ▼ standalone question
 ┌─ LangGraph Agent (agent ⇄ tools loop) ───────┐
 │ SystemPrompt: CTO advisor + full DB schema   │
 │ Tools:                                        │
 │ ① execute_readonly_query (SELECT-only MySQL) │
 │ ② summarize_report (today/امبارح/dates)      │
 │ ③ get_current_datetime (Africa/Cairo)        │
 │ ④ web_search (DuckDuckGo, external only)     │
 │ ⑤ get_database_schema                        │
 └──────────────────────┬───────────────────────┘
                        ▼ markdown answer (compact by default)
              MySQL persisted (sessions + messages)
```

> 🖨️ **Actual compiled LangGraph — printed live from code** (`app/services/chat_service.py:494-507`, `StateGraph` with nodes `agent` + `tools`):
> Regenerate anytime: `python -c "from app.services.chat_service import chat_service; print(chat_service.graph.get_graph().draw_mermaid())"`

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([__start__]):::first
	agent(agent)
	tools(tools)
	__end__([__end__]):::last
	__start__ --> agent;
	agent -. end .-> __end__;
	agent -.-> tools;
	tools --> agent;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

**How to read it:** `__start__ → agent` (LLM with tools bound, system prompt injected) → conditional router `_should_continue`: no `tool_calls` → `__end__` (reply to user) · has `tool_calls` → `tools` (`_tools_step` executes each call, returns `ToolMessage`s) → back to `agent` for the next reasoning round. The loop repeats until the agent answers without tools — then the reply is persisted to MySQL.

> 🔍 **Runtime zoom — what happens *inside* the `tools` node** (one fan-out per tool call):

```mermaid
flowchart TD
    START([__start__]) --> AGENT["🧠 agent node<br/>_agent_step<br/>system prompt + history<br/>llm.bind_tools 5 tools"]
    AGENT -- "no tool_calls<br/>_should_continue → end" --> FIN([__end__ → reply])
    AGENT -- "tool_calls<br/>_should_continue → tools" --> TOOLS["🔧 tools node<br/>_tools_step<br/>dispatch by name"]
    TOOLS --> Q["① execute_readonly_query<br/>SELECT-only MySQL · 50-row cap"]
    TOOLS --> R["② summarize_report<br/>today/امبارح/dates"]
    TOOLS --> D["③ get_current_datetime<br/>Africa/Cairo"]
    TOOLS --> W["④ web_search<br/>DuckDuckGo external-only"]
    TOOLS --> S["⑤ get_database_schema"]
    Q & R & D & W & S --> BACK["ToolMessages → back to agent"]
    BACK --> AGENT
```

- **Sessions sidebar:** `New Chat` · auto-titled from first message · per-session history · delete. Memory window = `CHAT_MEMORY_WINDOW_SIZE` (default **10**), rewrite window = `CHAT_QUERY_REWRITE_WINDOW_SIZE` (default **2**).
- **Response discipline:** compact lists (PR # + title + author + state, max ~10) → full details only for one explicitly requested PR; human timestamps (`10 أكتوبر، 13:09`, never raw ISO); one reply = one language; technical identifiers never translated.
- **Smart follow-ups:** pronouns/ordinals resolved deterministically — *"اه التانيه"* after a `[#10, #7, #3]` list → details of **PR #7**; explicit numbers beat positions (`PR #2` wins over list position 2).
- **Report questions** (`لخص ريبورت النهاردة`, `summarize yesterday's report`) route to `summarize_report`, which parses `today/امبارح/YYYY-MM-DD/DD month` in AR+EN and caps summaries at 2000 chars.
- **Read-only fortress:** regex-allowed `SELECT/SHOW/DESCRIBE/EXPLAIN` only + forbidden-keyword block (`INSERT/UPDATE/DELETE/DROP/…`) + `SET TRANSACTION READ ONLY` + 50-row cap.
- Files: `app/services/chat_service.py` (≈750 lines: prompts, tools, graph, ordinal resolver, session CRUD) · `app/models/chat_model.py` · endpoints `GET/POST /api/chat/sessions…`

<details>
<summary><b>🧪 Try these prompts (copy-paste)</b></summary>

- `List open PRs with authors and impact scores`
- `Who are the top 3 engineers this month and why?`
- `Which PRs are overdue right now?`
- `لخص ريبورت النهاردة`
- `مين أكتر حد عمل PRs آخر 30 يوم؟`
- `What time is it in Cairo?`
- `Search the web: what is trunk-based development?`

</details>

---

### 6 · 📄 Daily CTO Reports — 08h00 Executive Brief

**Wake up to a finished brief.** Every morning the system writes your exec summary *for you* — metrics + AI analysis + styled PDF.

```mermaid
flowchart LR
    A["⏰ Celery Beat<br/>08:00 Africa/Cairo"] --> B["Celery Worker<br/>reports.generate_daily"]
    B --> C["① Deterministic metrics<br/>collect_daily_metrics (no LLM)<br/>opened/merged/closed 24h<br/>newly-overdue · ranked engineers"]
    C --> D["② AI deep analysis<br/>Bedrock/Groq + read-only schema<br/>summary · bottlenecks<br/>recommendations · performers"]
    D --> E["③ Styled PDF<br/>reportlab + Amiri font<br/>KPI table · engineers · overdue"]
    E --> F["reports/*.pdf + daily_reports row"]
    F --> G["UI: Preview inline / Download"]
```

- **Hybrid = trustworthy:** numbers are computed in pure Python (never hallucinated); the LLM only *interprets* them under strict rules (English-only, plain text, no markdown tables, usernames stay Latin).
- **PDF anatomy:** title `CTO Daily Report — YYYY-MM-DD` · explicit timestamp `2026-10-11 08:00 (UTC+03:00)` · KPI strip (Opened/Merged/Closed/Newly-Overdue/Open-Total) · engineers table · newly-overdue list · executive analysis (Arabic-shaped via `arabic-reshaper` + `python-bidi`, Amiri font bundled in `app/services/fonts/`).
- **UI:** reports table (`Report` · `Date & Time` · `Opened` · `Merged` · `Overdue` · `PDF` with Preview/Download) served by `GET /api/reports/{id}/file?mode=preview|download`.
- **Manual run (no waiting for morning):**
  ```powershell
  curl.exe -X POST http://localhost:8000/api/reports/generate
  curl.exe http://localhost:8000/api/reports/tasks/<task_id>
  curl.exe http://localhost:8000/api/reports
  ```
- Files: `app/services/report_service.py` · `app/services/celery_app.py` · `app/models/report_model.py` · migration `0002_daily_reports.py` · output dir `reports/`

---

### 7 · 🎙️ Voice Agent — Deepgram Live Copilot

**Hands-free CTO.** Click *Start Voice Call*, talk naturally, hear live metrics — the agent queries MySQL mid-sentence.

```mermaid
sequenceDiagram
    participant Mic as 🎤 Browser Mic (PCM 16kHz)
    participant App as FastAPI /api/voice/ws
    participant DG as Deepgram Agent (nova-3 + aura-asteria-en)
    participant DB as MySQL (read-only)
    Mic->>App: binary audio frames
    App->>DG: relay audio
    DG-->>App: transcript + FunctionCallRequest{execute_database_query, sql_query}
    App->>App: show 🔍 Querying MySQL badge
    App->>DB: SELECT-only execution (30-row cap)
    DB-->>App: JSON rows
    App->>DG: FunctionCallResponse{content}
    DG-->>App: TTS audio (24kHz) + transcript events
    App->>Mic: playback + live transcript log
```

- **Orb stage:** idle → listening → thinking → speaking states with ripple animation; status pill (`Ready to Connect` → `Live`); mute button; barge-in notice.
- **DB tool discipline:** same read-only guard as chat (`SELECT`-only + forbidden-keyword block + read-only transaction), results capped at 30 rows for concise speech; daily-report questions run a fixed highlights query and point to the full PDF in the Reports tab.
- **Bridge robustness:** `parse_function_calls()` tolerates Deepgram's JSON-encoded-string `arguments` shape and never crashes the relay loop; missing `DEEPGRAM_API_KEY` fails gracefully with an explanatory socket error.
- Endpoints: `GET /api/voice/config` (readiness + models) · `WS /api/voice/ws` (bidirectional audio+events).
- Files: `app/services/voice_service.py` · voice view in `web/index.html` + `web/app.js`

---

### 8 · 🔐 Access Gate — Password + TOTP

**The whole app sits behind one locked door** — pages *and* APIs — except `/login`, `/api/auth/*`, `/api/health`, `/api/webhook/*`, `/static/*`, docs. GitHub webhooks keep working by design.

```mermaid
flowchart TD
    U["Visitor"] --> C{"Enrolled?"}
    C -- No --- P1["Enter CTO_PASSWORD"] --> Q["Scan QR in Google Authenticator"] --> V1["Enter 6-digit code"] --> IN["✅ Logged in"]
    C -- Yes --- P2["Password + current 6-digit code"] --> IN
    IN --> R{"Remember device?"} -- Yes --- RM["Remember cookie (REMEMBER_ME_DAYS=7)"]
    R -- No --- S["Session cookie (SESSION_MAX_AGE_HOURS=12)"]
    P2 -->|3 bad tries| L["🔒 IP lockout 30 min"]
```

- **Setup:** set `CTO_PASSWORD` + `SESSION_SECRET` (`python -c "import secrets; print(secrets.token_urlsafe(32))"`), `docker compose up -d`, open app, scan QR, enter code. Tick **Remember this device** to skip login for 7 days.
- **Crypto:** TOTP secret Fernet-encrypted in `auth_state` table (migration `0003`); rotating `SESSION_SECRET` invalidates old secrets + cookies (forced re-enrollment). Fail-closed: empty password/secret ⇒ logins refused.
- **Ops:** `POST /api/auth/totp/reset` (logged-in) wipes enrollment for a fresh QR; brute force throttled (`AUTH_MAX_ATTEMPTS` / `AUTH_LOCKOUT_SECONDS`).
- Files: `app/core/auth_gate.py` · `app/services/auth_service.py` · `app/api/auth.py` · `app/models/auth_model.py` · `web/login.html`

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph Edge ["🌍 Edge"]
        GH["GitHub<br/>poll + webhooks"]
        USER["CTO Browser<br/>SPA + voice mic"]
    end
    subgraph App ["🐳 Docker Compose — 5 services"]
        API["cto-copilot (FastAPI :8000)<br/>REST + WS + static SPA<br/>AuthGate middleware"]
        WORKER["cto-worker (Celery)<br/>report generation"]
        BEAT["cto-beat (Celery Beat)<br/>daily 08:00 trigger"]
        REDIS[("redis:7<br/>broker + results")]
        MYSQL[("mysql:8<br/>cto_copilot_db<br/>utf8mb4")]
    end
    subgraph AI ["🧠 AI Providers (external)"]
        BED["Bedrock Mantle<br/>Qwen3-32B (primary)"]
        GROQ["Groq<br/>gpt-oss-20b → 120b (fallback)"]
        JEV["TypeSafe JEV<br/>impact 1-10"]
        DG["Deepgram<br/>nova-3 + aura voice"]
    end
    GH -->|REST + webhook| API
    USER <-->|HTTP + WebSocket| API
    API <--> REDIS
    API <--> MYSQL
    WORKER <--> REDIS
    WORKER <--> MYSQL
    BEAT --> REDIS
    API --> BED
    API --> GROQ
    API --> JEV
    API <--> DG
```

| Container | Image / Command | Ports | Role |
|---|---|---|---|
| `cto-copilot-mysql` | `mysql:8.0` | `3307→3306` | System of record (PRs, engineers, chat, reports, auth) |
| `cto-copilot-redis` | `redis:7-alpine` | `6379` | Celery broker + result backend |
| `cto-copilot-app` | `uvicorn app.main:app` | `8000→8000` | API + SPA + polling + auth gate |
| `cto-copilot-worker` | `celery worker --concurrency=2` | — | Executes daily-report pipeline |
| `cto-beat` | `celery beat` | — | Fires `reports.generate_daily` at 08:00 Cairo |

Healthchecks on all three infra services; app hot-mounts `./app`, `./web`, `./reports` for live iteration.

---

## 🧠 AI Brain — Bedrock + Groq + JEV

### Circuit breaker (never go dark)

```mermaid
stateDiagram-v2
    [*] --> CLOSED: startup (Bedrock primary)
    CLOSED --> OPEN: Bedrock call fails<br/>(record failure, start cooldown)
    OPEN --> HALF_OPEN: cooldown elapsed (1800s default)
    HALF_OPEN --> CLOSED: probe ping succeeds ✅
    HALF_OPEN --> OPEN: probe fails (extend Groq fallback)
    OPEN --> OPEN: requests → Groq directly
```

- Probe prompt = `CIRCUIT_BREAKER_PROBE_PROMPT` (`ping`, 5 tokens, 10s timeout).
- Live status: `GET /api/circuit-breaker` → `{state, cooldown_seconds, seconds_remaining, active_provider}` (also inside `/api/health`).
- File: `app/services/circuit_breaker.py`

### Provider chain

| Layer | Model | Via | When |
|---|---|---|---|
| 🥇 Primary | `qwen.qwen3-32b` (Bedrock Mantle, OpenAI-compatible) | `openai.OpenAI(base_url=…/v1)` | Circuit CLOSED / recovered |
| 🥈 Fallback | `openai/gpt-oss-20b` → `openai/gpt-oss-120b` | LangChain `ChatGroq` | Circuit OPEN / Bedrock error |
| ⚖️ Scorer | `jev-latest` (TypeSafe SystemOne) | `JEV_API_URL` decision API | Every summarization (default 5.0 if unconfigured) |

Hyperparameters: `LLM_TEMPERATURE=0.2` · `LLM_MAX_TOKENS=1024` — deterministic, executive-dense output.

---

## 🗄️ Data Model — MySQL + Alembic

```mermaid
erDiagram
    PULL_REQUESTS ||--o{ ENGINEERS : "aggregated into (rebuild_engineers)" 
    PULL_REQUESTS {
        int id PK
        int number UK
        string title
        string author
        string state
        string head_branch
        string base_branch
        datetime created_at
        datetime updated_at
        bool is_overdue
        int overdue_days
        text summary_text
        string summary_provider
        float impact_score
        string impact_tier
    }
    ENGINEERS {
        int id PK
        string author UK
        int pr_count
        float total_score
        float avg_score
        string tier
    }
    DAILY_REPORTS {
        int id PK
        date report_date UK
        string title
        text executive_summary
        int prs_opened
        int prs_merged
        int prs_closed
        int overdue_count
        string pdf_path
    }
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : contains
    CHAT_SESSIONS {
        string id PK
        string title
    }
    CHAT_MESSAGES {
        int id PK
        string session_id FK
        string role
        text content
    }
    AUTH_STATE {
        int id PK
        string totp_secret_encrypted
    }
```

- Migrations: `0001_initial_two_tables` (PRs + engineers) · `0002_daily_reports` · `0003_auth_state`. App container runs `alembic upgrade head` on startup — plain `docker compose up` keeps schema current.
- Migration workflow: change `app/models/*` → `python -m alembic revision --autogenerate -m "msg"` → review → `upgrade head` → `pytest` → rebuild `cto-copilot`.
- From your terminal (outside Docker) point at the published port: `$env:MYSQL_HOST="127.0.0.1"; $env:MYSQL_PORT="3307"; python -m alembic current|history|upgrade head|stamp head` — `.env` keeps `MYSQL_HOST=mysql` for in-network containers.

---

## 📡 API Reference

### PRs & Intelligence

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health + repo + circuit-breaker status |
| `GET` | `/api/prs?state=all\|open\|closed` | PR list with summaries, scores, SLA flags |
| `GET` | `/api/dashboard?days=1..365` | Leaderboard + timeframe label + overdue PRs |
| `POST` | `/api/prs/{n}/summarize?force_refresh=false` | (Re)generate summary + JEV score for one PR |
| `GET` | `/api/circuit-breaker` | Breaker state + cooldown countdown |
| `POST` | `/api/webhook/github` | GitHub `pull_request` events → auto-summarize |
| `GET` | `/api/db/stats` | Row counts (`pull_requests`, `engineers`) |
| `GET` | `/api/engineers` | Engineers with PR count / total / avg score |

### Chat (LangGraph)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/chat/sessions` | List conversations |
| `POST` | `/api/chat/sessions` | Create session (`{title?}`) |
| `GET` | `/api/chat/sessions/{id}/messages` | History |
| `DELETE` | `/api/chat/sessions/{id}` | Delete session + messages |
| `POST` | `/api/chat/sessions/{id}/message` | Send `{message}` → `{reply, rewritten_query}` |

### Reports

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/reports?limit=30` | List reports, newest first |
| `POST` | `/api/reports/generate` | Enqueue generation → `{task_id}` (inline fallback if Redis down) |
| `GET` | `/api/reports/tasks/{task_id}` | `PENDING / SUCCESS / FAILURE` + result |
| `GET` | `/api/reports/{id}/file?mode=preview\|download` | Inline PDF vs attachment download |

### Voice

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/voice/config` | `{configured, model, voice}` readiness |
| `WS` | `/api/voice/ws` | Bidirectional audio + transcript + DB-tool events |

### Auth Gate

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/auth/status` | `{enrolled, configured}` for login UI |
| `POST` | `/api/auth/setup` | Begin TOTP enrollment (password-gated) |
| `POST` | `/api/auth/verify` | Confirm code → finish enrollment + login |
| `POST` | `/api/auth/login` | Password (+code) + optional `remember` |
| `POST` | `/api/auth/logout` | Clear session + remember cookies |
| `POST` | `/api/auth/totp/reset` | Wipe enrollment (authed) → fresh QR |

---

## ⚙️ Configuration — .env Cheat Sheet

Copy `.env.example` → `.env` and fill secrets. **Never commit `.env`.**

| Group | Keys | Notes |
|---|---|---|
| GitHub | `GITHUB_TOKEN` · `GITHUB_REPO` · `GITHUB_API_URL` · `GITHUB_POLL_INTERVAL_SECONDS=30` · `PR_STALE_THRESHOLD_DAYS=5` | Token needs `repo` read; poll drives auto-summaries |
| Bedrock | `BEDROCK_API_KEY` · `BEDROCK_BASE_URL_QWEN` · `BEDROCK_MODEL=qwen.qwen3-32b` · `BEDROCK_VISION_MODEL` | Primary summarizer |
| JEV | `JEV_API_KEY` · `JEV_API_URL` · `JEV_MODEL=jev-latest` | Impact 1–10; missing key ⇒ neutral 5.0 |
| Groq | `GROQ_API_KEY` · `GROQ_MODEL` · `GROQ_BACKUP_MODEL` | Fallback chain `20b → 120b` |
| Tuning | `LLM_TEMPERATURE=0.2` · `LLM_MAX_TOKENS=1024` | Executive-dense, low-variance |
| Breaker | `CIRCUIT_BREAKER_COOLDOWN_SECONDS=1800` · `CIRCUIT_BREAKER_PROBE_PROMPT=ping` | 30-min fallback window |
| App | `APP_HOST` · `APP_PORT=8000` · `STATIC_DIR=web` | — |
| MySQL | `MYSQL_HOST=mysql` · `MYSQL_PORT=3306` · `MYSQL_USER/PASSWORD/DATABASE` · `DATABASE_URL=` | Compose overrides host/port; CLI uses `127.0.0.1:3307` |
| Chat | `CHAT_MEMORY_WINDOW_SIZE=10` · `CHAT_QUERY_REWRITE_WINDOW_SIZE=2` | Short-term memory + follow-up rewrite |
| Celery | `CELERY_BROKER_URL` · `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` |
| Reports | `REPORT_TIMEZONE=Africa/Cairo` · `REPORT_HOUR=8` · `REPORT_MINUTE=0` · `REPORTS_DIR=reports` · `REPORT_LANGUAGE=English` | English-only keeps PDFs LTR-clean |
| Voice | `DEEPGRAM_API_KEY` · `DEEPGRAM_AGENT_MODEL=nova-3` · `DEEPGRAM_VOICE_MODEL=aura-asteria-en` | Missing key ⇒ voice gracefully disabled |
| Gate | `CTO_PASSWORD` · `SESSION_SECRET` · `SESSION_MAX_AGE_HOURS=12` · `REMEMBER_ME_DAYS=7` · `TOTP_ISSUER` · `AUTH_MAX_ATTEMPTS` · `AUTH_LOCKOUT_SECONDS` | Fail-closed when empty |

---

## 🚀 Quick Start — Run in 60 Seconds

```powershell
# 1 · configure
Copy-Item .env.example .env
# edit .env → GITHUB_TOKEN, CTO_PASSWORD, SESSION_SECRET (see Gate section), LLM keys

# 2 · launch the whole stack (mysql + redis + app + worker + beat)
docker compose up -d --build

# 3 · open
Start-Process http://localhost:8000/
Start-Process http://localhost:8000/docs
```

```powershell
# useful ops
docker compose logs -f cto-copilot        # app logs
docker compose logs -f cto-worker        # report worker
curl.exe http://localhost:8000/api/health
curl.exe -X POST http://localhost:8000/api/reports/generate

# local dev (no docker for the API itself)
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
python -m pytest tests/ -v
```

**GitHub webhook (for instant summaries):** repo Settings → Webhooks → Payload URL `https://<your-host>/api/webhook/github` → Content type `application/json` → events: *Pull requests* → Active. No auth header needed (endpoint is gate-exempt by design).

---

## 🗂️ Project Structure

```
CTO_MULTI_AGENT/
├── app/
│   ├── main.py                  # FastAPI app + CORS + AuthGate + static SPA + poll loop
│   ├── core/
│   │   ├── config.py            # pydantic-settings (.env → Settings)
│   │   ├── enums.py             # PRStatus · LLMProvider · CircuitBreakerState · prompts
│   │   └── auth_gate.py         # login-gate middleware (allowlist inside)
│   ├── api/
│   │   ├── routes.py            # PRs · dashboard · chat · reports · voice WS · webhooks
│   │   └── auth.py              # setup/verify/login/logout/totp-reset
│   ├── services/
│   │   ├── github_service.py    # poll · diff · summarize · dashboard · SLA math
│   │   ├── llm_service.py       # Bedrock primary → Groq fallback (breaker-aware)
│   │   ├── jev_service.py       # TypeSafe JEV impact 1–10
│   │   ├── circuit_breaker.py   # CLOSED/OPEN/HALF_OPEN + probe
│   │   ├── chat_service.py      # LangGraph agent · 5 tools · rewrite · sessions
│   │   ├── voice_service.py     # Deepgram bridge · read-only SQL tool
│   │   ├── report_service.py    # metrics → AI analysis → PDF (Amiri font)
│   │   ├── celery_app.py        # worker + beat schedule (08:00 Cairo)
│   │   ├── db_service.py        # MySQL upserts · engineers rebuild · reports CRUD
│   │   └── auth_service.py      # password+TOTP · Fernet · cookies · rate limit
│   ├── models/                  # pr · engineer · chat · report · auth (SQLAlchemy)
│   ├── schemas/                 # PRItem · DashboardLeaderboardResponse · …
│   └── db/                      # async engine + session factory
├── web/
│   ├── index.html               # 7 views: home/prs/overdue/dashboard/chat/reports/voice
│   ├── app.js                   # ~1190 lines: fetch · render · chat · voice WS · drawer
│   ├── style.css                # design system (Plus Jakarta Sans)
│   └── login.html               # password → QR → TOTP → remember-me
├── alembic/versions/            # 0001 two-tables · 0002 reports · 0003 auth_state
├── tests/                       # 8 suites: auth · chat · rewrite · reports · voice · migrations
├── reports/                     # generated daily PDFs (git-ignored artefacts)
├── docs/screenshots/            # ← drop sanitized captures here (see table above)
├── docker-compose.yml           # mysql · redis · app · worker · beat
├── Dockerfile                   # python:3.12-slim + uvicorn
└── requirements.txt             # fastapi · langgraph · celery · reportlab · …
```

---

## 🧪 Testing

| Suite | Covers |
|---|---|
| `test_alembic_migrations.py` | Migration chain builds on SQLite |
| `test_auth.py` | Gate: enroll → verify → login → lockout → reset |
| `test_chat_language.py` | AR/EN reply-language discipline |
| `test_chat_query_rewrite.py` | Follow-up/ordinal rewriting (incl. `اه التانيه`) |
| `test_chat_report_tool.py` | Report-date parsing (AR+EN) + summarizer |
| `test_chat_search_voice.py` | Web-search + datetime tools |
| `test_daily_reports.py` | 24h metrics determinism + PDF build |
| `test_voice_agent.py` | Function-call parsing + read-only SQL guard |

```powershell
python -m pytest tests/ -v
```

SQLite-backed — no MySQL/Redis needed for unit tests.

---

## 🛡️ Security & Guardrails

- 🔒 **Fail-closed gate** — empty `CTO_PASSWORD`/`SESSION_SECRET` ⇒ all logins refused.
- 🔑 **Fernet-encrypted TOTP** at rest; rotation forces re-enrollment.
- 🚫 **SQL fortress** — chat + voice accept `SELECT`-family only, keyword blacklist, read-only transactions, row caps (50 chat / 30 voice).
- 🧠 **Prompt-injection aware** summarizer — PR content treated as untrusted data, never as instructions.
- ⏳ **Rate-limited auth** + IP lockout; HttpOnly `SameSite=Lax` cookies.
- 🕊️ **Webhook minimalism** — only `opened/synchronize/reopened` trigger work; everything else ignored.

---

## 🗺️ Roadmap

- [ ] Screenshot gallery auto-capture (`docs/screenshots/` CI job with redaction)
- [ ] PR review-risk score (conflict probability + blast radius)
- [ ] Slack/Teams push for overdue + daily PDF delivery
- [ ] Per-engineer weekly digest + trend charts
- [ ] Vision diffs (Bedrock Nova Pro) for UI-heavy PRs
- [ ] SSO (GitHub OAuth) alongside the shared gate

---

## 🤝 Contributing

1. Fork → branch (`feat/…`) → change `app/models/*` if needed → `alembic revision --autogenerate` → review migration → `pytest` → PR.
2. Sanitize screenshots (blur titles/avatars) before adding to `docs/screenshots/`.
3. Never commit `.env` or API keys — `.env.example` holds placeholders only.

---

<div align="center">

**Built for CTOs who'd rather lead than chase PRs.** 🛰️
<br>
<i>CTO Watch — see everything, miss nothing.</i>

</div>
