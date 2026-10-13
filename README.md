<div align="center">

# 🛰️ CTO Watch — Engineering Leadership Hub
### *CTO-Copilot · Your AI Command Center for Team Velocity, PR Intelligence & Executive Insight*

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](./docker-compose.yml)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](./alembic/versions/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](./docker-compose.yml)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-7C3AED?style=for-the-badge)](./app/services/chat_service.py)
[![Bedrock](https://img.shields.io/badge/Bedrock-GPT_OSS_120B-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)](./app/services/llm_service.py)
[![Groq](https://img.shields.io/badge/Groq-Fallback-F55036?style=for-the-badge)](./app/services/llm_service.py)
[![Deepgram](https://img.shields.io/badge/Deepgram-Voice_Agent-13EF93?style=for-the-badge)](./app/services/voice_service.py)
[![Celery](https://img.shields.io/badge/Celery-Beat_08:00-37814A?style=for-the-badge)](./app/services/celery_app.py)

**One dashboard to rule all PRs. AI summaries in seconds. Impact-ranked engineers. A chatbot that *queries your live database*. A voice agent you can talk to. Daily PDF reports on your desk at 08:00. All behind a password + Google Authenticator gate.**

[🚀 Quick Start](#-quick-start--run-in-60-seconds) · [✨ Features](#-feature-atlas--every-screen-dissected) · [📸 Showcase](#-visual-showcase--live-screenshots) · [🏗️ Architecture](#️-system-architecture) · [🤖 AI Stack](#-ai-brain--bedrock--groq--jev) · [📡 API](#-api-reference) · [⚙️ Config](#️-configuration--env-cheat-sheet)

</div>

---

## 🧭 Product Tour (Screenshots)

| Screen | Preview | What you're looking at |
|---|---|---|
| 🏠 **Home — Team Velocity & Pulse** | <img src="docs/screenshots/01-home.png" alt="Home view — SLA health card and weekly activity chart" width="420"> | Live SLA Health card (% within SLA + bar) + 7-day Opened-vs-Merged SVG chart |
| 🔀 **PR Requests Directory** | <img src="docs/screenshots/02-pr-requests.png" alt="PR Requests table with AI summaries and scores" width="420"> | Auto-populated PR table: author · date · executive AI summary · state · impact score · details link + `All/Open/Merged/Closed` filters |
| ⚠️ **Overdue / SLA Alerts** | <img src="docs/screenshots/03-overdue.png" alt="Overdue PRs table with SLA countdown" width="420"> | Every open PR older than `PR_STALE_THRESHOLD_DAYS` (default **8**) with overdue-duration counter |
| 🏆 **Engineer Impact Dashboard** | <img src="docs/screenshots/04-dashboard.png" alt="Leaderboard ranked by impact" width="420"> | Leaderboard ranked by **impact, not commit count** — 8 time windows (Today → 1 Year), avg/total impact, tier badges |
| 💬 **CTO AI Copilot (Chat)** | <img src="docs/screenshots/05-chatbot.png" alt="Chat sessions sidebar and messages" width="420"> | LangGraph agent with live read-only MySQL access, sessions sidebar, bilingual AR/EN, query-rewrite for follow-ups |
| 📄 **Daily CTO Reports** | <img src="docs/screenshots/06-reports.png" alt="Daily reports table with preview and download" width="420"> | One PDF every morning at **08:00 Africa/Cairo** — Preview inline / Download attachment |
| 🎙️ **Voice Copilot** | <img src="docs/screenshots/07-voice.png" alt="Voice orb visualizer with transcript" width="420"> | Push-to-talk Deepgram agent: glowing orb · live transcript · real-time `🔍 Querying MySQL:` badge |
| 🔐 **Access Gate** | <img src="docs/screenshots/08-login.png" alt="Password plus TOTP login" width="420"> | Shared password → QR enroll in Google Authenticator → 6-digit TOTP → optional *Remember this device* |
| 📧 **Email Triage** | <img src="docs/screenshots/09-email.png" alt="Email triage table" width="420"> | Unread mail auto-summarized & urgency-scored (1–10) |
| 🧭 **Workspace Menu** | <img src="docs/screenshots/10-menu.png" alt="Workspace menu drawer" width="420"> | Slide-out drawer with live badge counts |
| 🧪 **Eval Lab** | <img src="docs/screenshots/11-eval.png" alt="Eval Lab benchmarks" width="420"> | Hallucination torture suite scored in MLflow (98% faithful / 0% hallucination) |
| 📢 **Slack Bot Integration** | <img src="docs/screenshots/12-slack.png" alt="Slack alert delivery" width="420"> | Morning PDF report upload + SLA breach cards |

---

## 📸 Visual Showcase — Live Screenshots

*Real captures from the running app — no mockups. Walk the product top to bottom, exactly as a CTO would on day one.*

### 🔐 Access Gate — Password + TOTP

The whole app sits behind one locked door — pages *and* APIs. Shared password first, then a 6-digit Google Authenticator code (QR enroll on first setup, *Remember this device* for 7 days).

![Sign in — password gate](docs/screenshots/00-access-gate-signin.png)
![Sign in — authenticator code](docs/screenshots/01-access-gate-totp.png)

### 🏠 Home — Team Velocity & Engineering Pulse

The 10-second executive glance: live SLA Health (100% here — 1 within SLA, 0 breached) plus the 7-day Opened-vs-Merged chart, computed from real PRs on every visit.

![Team Velocity and Engineering Pulse](docs/screenshots/02-home-velocity.jpg)

### 🔀 PR Requests — Automated PR Intelligence

Every GitHub PR auto-fetched, auto-summarized (diff-grounded, 2–3 dense sentences), auto-scored 1–10 by JEV — with `All / Open / Merged / Closed` filters and one-click re-sync.

![Pull Requests Directory](docs/screenshots/03-pr-requests.jpg)

### ⚠️ Overdue — SLA Radar

Silent rot gets flagged before it bottlenecks: any open PR past the threshold (8 days here) lands here with an overdue-duration counter. All clear right now — the healthy green state.

![Overdue Pull Requests](docs/screenshots/04-overdue-sla.jpg)

### 🏆 Dashboard — Engineer Impact

Ranked by architectural impact, not commit count — 8 time windows (Today → 1 Year), tiers from 🔴 Critical Driver to ⚪ Routine Support.

![Engineer Impact Dashboard](docs/screenshots/05-engineer-dashboard.jpg)

### 💬 Chatbot — CTO AI Copilot

Talk to your live database in Arabic or English. LangGraph agent over read-only MySQL with sessions, follow-up understanding, and a grounding gate that rejects fabricated numbers.

![CTO AI Copilot chat](docs/screenshots/06-ai-copilot-chat.jpg)

### 🧭 Workspace Menu — Everything One Click Away

Slide-out drawer with live count pills (`PRs: 5` · `Overdue: 0` · `Emails: 4`) — know the state of the org before you even navigate.

![Workspace menu with live counts](docs/screenshots/07-workspace-menu.jpg)

### 📄 Daily CTO Reports — 08:00 Executive Brief

Deterministic metrics (never hallucinated) + AI executive analysis + styled PDF, every morning — Preview inline or Download.

![Daily CTO Reports](docs/screenshots/08-daily-reports.jpg)

> 📝 *The timestamps in this screenshot are from testing — production reports land every day at **08:00 Africa/Cairo** sharp.*

### 📧 Emails — Inbox Triage

Unread mail polled over strictly read-only IMAP, summarized by the same AI stack, urgency-scored 1–10 (🔴 Reply Now → ⚪ Archive). Nothing is ever marked read or auto-answered.

![Email triage](docs/screenshots/09-email-triage.jpg)

> 🕵️ *Senders and contents blurred for privacy — scores and tiers shown are real.*

### 🎙️ Voice Agent — Hands-Free CTO

Push-to-talk Deepgram copilot: glowing orb, live transcript, and a *Querying MySQL* badge while it fetches real metrics mid-sentence.

![Voice Copilot](docs/screenshots/10-voice-copilot.jpg)

### 🧪 Eval Lab — Hallucinations Measured, Not Vibes

~122 torture questions (adversarial traps + live-DB questions) scored in MLflow — **Judge ON: 98% faithful / 0% hallucination** vs OFF: 90%. That's the grounding gate's worth, proven with numbers.

![Eval Lab results](docs/screenshots/11-eval-lab.jpg)

### 📢 Slack Bot — Alerts Where You Work

SLA-breach Block Kit cards with one-click *Review on GitHub*, plus the morning PDF auto-uploaded to your channel after 08:00.

![Slack daily report delivery](docs/screenshots/12-slack-alerts.jpg)

---

## 📚 Table of Contents

- [📸 Visual Showcase — live screenshots](#-visual-showcase--live-screenshots)
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
  - [9 · Emails](#9--emails--inbox-triage)
  - [10 · Slack Bot](#10--slack-bot--sla-breach-radar--morning-pdf-broadcast)
  - [11 · Eval Lab](#11--eval-lab--torture-tests--mlflow)
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
- **Weekly PR Activity chart** — dependency-free SVG line chart over the last 7 local days: **Opened** (blue, by `created_at`) vs **Merged** (green, by `state + updated_at`), integer gridlines, day labels, totals footer. Only in-window activity is plotted — open PRs created *before* the window are named in the footer/empty state (`…still open from before`) so the chart never looks dead-wrong.
- **Refresh:** loads on first paint + every Home navigation + the global 25s background poll (`loadHome()` in `web/app.js`).
- **Navigation hub** — top bar (`Home` shortcut · `Team Online` presence · `Workspace Menu` drawer) + right slide-out drawer with live count pills (`PRs: N` · `Overdue: M`).
- Files: `web/index.html` (homeView) · `web/app.js` (`loadHome/renderSLA/renderWeeklyChart`) · `web/style.css` (`.sla-bar`, `.chart-card`, `.chart-line…`)

---

### 2 · 🔀 PR Requests — Automated PR Intelligence

**Every GitHub PR, auto-fetched, auto-summarized, auto-scored. Zero manual work.**

```
  GitHub ──poll every 30s──▶ FastAPI ──diff (≤100k chars)──▶ Bedrock GPT-OSS
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
3. Diff fetched with `Accept: application/vnd.github.v3.diff`, near-full (up to **100k chars**, flag `is_truncated` only for monster diffs that would blow the LLM timeout).
4. Prompt assembled from `UserPromptTemplate.PR_DIFF_TEMPLATE` (metadata + description + diff excerpt).
5. `LLMService.generate_pr_summary()` → Bedrock GPT-OSS primary, Groq fallback via circuit breaker.
6. `JevService.evaluate_impact(summary, diff)` → score **1.0–10.0** (TypeSafe `jev-latest`, 10-level criteria from *typo* → *platform upgrade*; scored from the diff first, summary as context, diff capped at 12k chars for the decision API).
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
- ⚠️ **Known limitations:** impact scores are AI judgments over diffs (monster diffs are capped; the score reflects what the model saw) — treat them as triage signals, not performance reviews. Ranking engineers by AI score is sensitive: use it to spot who needs support or who drove a release, never as a standalone appraisal tool.

---

### 5 · 💬 Chatbot — CTO AI Copilot (LangGraph Agent)

**Talk to your database.** Ask *"who's blocked?"*, *"summarize today's report"* (bilingual AR/EN support — responds in the prompt's language).

```
 User ("who's the second one? / and its author?")
   │
   ▼
 ┌─ Query Rewriter (LLM) ─────────────────────────┐
 │ follow-ups ("by whom?") → standalone question  │
 │ via model rewrite w/ history window           │
 └──────────────────────┬───────────────────────┘
                        ▼ standalone question
 ┌─ LangGraph Agent (agent ⇄ tools loop) ───────┐
 │ SystemPrompt: CTO advisor + full DB schema   │
 │ Tools:                                        │
 │ ① execute_readonly_query (SELECT-only MySQL) │
 │ ② summarize_report (today/yesterday/dates)   │
 │ ③ get_current_datetime (Africa/Cairo)        │
 │ ④ web_search (DuckDuckGo, external only)     │
 │ ⑤ get_database_schema                        │
 └──────────────────────┬───────────────────────┘
                        ▼ markdown answer (compact by default)
              MySQL persisted (sessions + messages)
```

> 🖨️ **Actual compiled LangGraph — printed live from code** (`app/services/chat_service.py:494-507`, `StateGraph` with nodes `agent` + `tools`).
> Node `classDef` colors are tuned for contrast (dark text on light nodes, white on dark) so the graph stays readable in both GitHub **light** and **dark** mode. Regenerate the structure anytime: `python -c "from app.services.chat_service import chat_service; print(chat_service.graph.get_graph().draw_mermaid())"`

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
	classDef default fill:#e0e7ff,stroke:#4338ca,stroke-width:2px,color:#1e1b4b
	classDef first fill:#0f172a,stroke:#94a3b8,stroke-width:2px,color:#f8fafc
	classDef last fill:#4f46e5,stroke:#312e81,stroke-width:2px,color:#ffffff
```

**How to read it:** `__start__ → agent` (LLM with tools bound, system prompt injected) → conditional router `_should_continue`: no `tool_calls` → `__end__` (reply to user) · has `tool_calls` → `tools` (`_tools_step` executes each call, returns `ToolMessage`s) → back to `agent` for the next reasoning round. The loop repeats until the agent answers without tools — then the reply is persisted to MySQL.

> 🔍 **Runtime zoom — what happens *inside* the `tools` node** (one fan-out per tool call):

```mermaid
flowchart TD
    START([__start__]) --> AGENT["🧠 agent node<br/>_agent_step<br/>system prompt + history<br/>llm.bind_tools 5 tools"]
    AGENT -- "no tool_calls<br/>_should_continue → end" --> FIN([__end__ → reply])
    AGENT -- "tool_calls<br/>_should_continue → tools" --> TOOLS["🔧 tools node<br/>_tools_step<br/>dispatch by name"]
    TOOLS --> Q["① execute_readonly_query<br/>SELECT-only MySQL · 50-row cap"]
    TOOLS --> R["② summarize_report<br/>today/yesterday/dates"]
    TOOLS --> D["③ get_current_datetime<br/>Africa/Cairo"]
    TOOLS --> W["④ web_search<br/>DuckDuckGo external-only"]
    TOOLS --> S["⑤ get_database_schema"]
    Q & R & D & W & S --> BACK["ToolMessages → back to agent"]
    BACK --> AGENT
```

- **Sessions sidebar:** `New Chat` · auto-titled from first message · per-session history · delete. Memory window = `CHAT_MEMORY_WINDOW_SIZE` (default **10**), rewrite window = `CHAT_QUERY_REWRITE_WINDOW_SIZE` (default **2**).
- **Response discipline:** compact lists (PR # + title + author + state, max ~10) → full details only for one explicitly requested PR; human timestamps (`Oct 10, 13:09`, never raw ISO); one reply = one language; technical identifiers never translated.
- **Smart follow-ups:** every follow-up (*"by whom?"*, *"and its author?"*) is rewritten by the LLM into a standalone question with history context — no hardcoded ordinal shortcuts, so nothing gets invented. A deterministic **time-guard** rejects any rewrite that drops time constraints (*today/yesterday…*) and keeps the original instead.
- **Report questions** (`summarize today's report`, `summarize yesterday's report`) route to `summarize_report`, which parses `today/yesterday/YYYY-MM-DD/DD month` and caps summaries at 2000 chars.
- **Read-only fortress:** regex-allowed `SELECT/SHOW/DESCRIBE/EXPLAIN` only + forbidden-keyword block + `SET TRANSACTION READ ONLY` + 50-row cap + cell coercion (`Decimal`/date/bytes → JSON-safe, so SUM/AVG results serialize instead of collapsing into Database Error).
- Files: `app/services/chat_service.py` (≈700 lines: prompts, tools, graph, LLM query-rewrite, session CRUD) · `app/models/chat_model.py` · endpoints `GET/POST /api/chat/sessions…`

#### 🛡️ Anti-Hallucination Grounding Gate — LLM-as-a-Judge

> **Zero tolerance for fabricated metrics:** In an executive engineering cockpit, hallucinations can be disastrous. If a CTO asks *"Which PRs breached SLA?"* or *"Who authored PR #12?"*, a standard model might invent plausible-sounding names or numbers. To reduce hallucinations to the absolute minimum, CTO Watch incorporates a dedicated **LLM-as-a-Judge** verification layer (`app/services/judge_service.py`) running an independent model (`openai.gpt-oss-20b`) that audits every single answer against real data before the user ever sees it.

```mermaid
flowchart TD
    RESP["🤖 Generated Agent Reply<br/>(qwen.qwen3-32b via Tools)"] --> DET{"① Deterministic Gate<br/>(Zero-cost regex)"}
    
    DET -- "Cited PR #N not in tool observations" --> FAIL_RETRY["❌ Instant FAIL<br/>Fabricated PR detected"]
    DET -- "Valid PR refs or no #N refs" --> SKIP{"② Claim Check<br/>Any numbers/digits/metrics?"}
    
    SKIP -- "No factual claims (e.g. 'Hello!')" --> DELIVER["✅ PASS → Deliver to CTO"]
    SKIP -- "Contains numbers, dates, or counts" --> JUDGE["⚖️ LLM Judge (openai.gpt-oss-20b)<br/>Audits reply against Tool Observations<br/>(The only source of ground truth)"]
    
    JUDGE --> VERDICT{"Verdict?"}
    VERDICT -- "PASS" --> DELIVER
    VERDICT -- "FAIL" --> RETRY{"Retry count < 1?"}
    
    FAIL_RETRY --> RETRY
    RETRY -- "Yes (Attempt 1)" --> REGEN["🔄 Grounded Self-Correction<br/>Re-prompt agent with bad_claims"] --> RESP
    RETRY -- "No (Retry failed)" --> FALLBACK["🛡️ Safe Grounded Fallback<br/>Refuses unverified metrics<br/>CTO never sees fake data"]
```

- **Tier 1 — Free Deterministic Guard:** Instantly cross-checks all cited PR numbers (`#N`) against raw tool output. If the agent mentions a PR number it never actually fetched, the response is rejected immediately at zero LLM cost.
- **Tier 2 — Claim Skip Optimization:** Pure conversational smalltalk without factual or countable claims skips the judge model entirely to eliminate unnecessary latency.
- **Tier 3 — Semantic LLM Judge (`openai.gpt-oss-20b`):** An independent, objective model audits the claims strictly against tool observations (the only ground truth). It outputs a structured JSON verdict: `{"verdict": "PASS" | "FAIL", "reason": "...", "bad_claims": [...]}`.
- **Self-Correction & Fallback Loop:** On `FAIL`, the agent receives one chance to self-correct using explicit feedback highlighting unsupported claims. If it fails again, it serves a safe fallback message rather than risking hallucinated data. Toggle via `JUDGE_ENABLED=true` in `.env`.

<details>
<summary><b>🧪 Try these prompts (copy-paste)</b></summary>

- `List open PRs with authors and impact scores`
- `Who are the top 3 engineers this month and why?`
- `Which PRs are overdue right now?`
- `Summarize today's report`
- `Who opened the most PRs in the last 30 days?`
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
- **Known limitation:** the voice speaks English only (`aura-asteria-en`) — unlike the bilingual text chatbot. Arabic speech in/out is not supported by the current voice stack.
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

### 9 · 📧 Emails — Inbox Triage

**Your inbox, triaged like your PRs.** Unread mail is polled over IMAP (strictly read-only), summarized by the same Bedrock/Groq stack, and scored 1–10 for reply-urgency by the JEV decision model.

```mermaid
flowchart LR
    A["📬 Gmail IMAP<br/>UNSEEN, readonly=True"] --> B["poll (beat every N min<br/>+ manual Sync Inbox)"]
    B --> C["① Upsert by Message-ID<br/>skip already-triaged"]
    C --> D["② AI summary<br/>Bedrock/Groq + email prompt"]
    D --> E["③ JEV urgency 1-10<br/>Reply Now → Archive"]
    E --> F["emails table<br/>migration 0004"]
    F --> G["UI: From · Subject · Date<br/>Summary · Score · Tier"]
```

- **Urgency tiers:** 🔴 `Reply Now ≥8` · 🟠 `Reply Today ≥6.5` · 🔵 `FYI / Soon ≥5` · ⚪ `Archive <5`.
- **List shows the last 3 days** (`GET /api/emails?days=N`, default 3) — newest first, undated rows sink to the bottom.
- **Summaries describe only** (who wrote what, facts only) — the LLM never suggests replies or actions; urgency lives in the score column, not the text.
- **Dismiss button** (✕ per row, `DELETE /api/emails/{id}`): soft-hides from the list to cut clutter; hidden mail stays in the DB so later polls never resurrect it.
- **Read-only by design:** mailbox opened `readonly=True` — nothing is marked read, moved, or deleted. No auto-replies, ever.
- **Privacy:** bodies are truncated (`EMAIL_MAX_BODY_CHARS`) before summarization; credentials live only in `.env` (gitignored) — never in screenshots or docs.
- **Setup:** enable 2FA on Google → create an App Password → set `EMAIL_ENABLED=true` + `EMAIL_ADDRESS` + `EMAIL_PASSWORD` in `.env` → `docker compose up -d` → open Emails → Sync Inbox.
- **Chatbot sees it too:** the `emails` table is in the agent's schema, so *"any urgent emails?"* works out of the box.
- Files: `app/services/email_service.py` · `app/models/email_model.py` · `app/api/routes.py` (`/api/emails*`) · `app/services/celery_app.py` (`emails.poll_inbox`) · migration `0004_emails.py`

---

### 10 · 📢 Slack Bot — SLA Breach Radar & Morning PDF Broadcast

**Engineering leadership alerts where you actually work.** Instant notifications when PRs breach review SLAs, plus automated morning PDF uploads of the daily executive briefing directly to your Slack channel.

```mermaid
flowchart LR
    A["Pull Request breached<br/>(age >= PR_STALE_THRESHOLD_DAYS)"] --> B["🚨 SLA Breach Alert<br/>Rich Block Kit + Review button"]
    C["Daily Report generated<br/>(08:00 Africa/Cairo)"] --> D["📄 Modern File Upload<br/>files.uploadV2 external flow"]
    B --> E["💬 Slack Channel<br/>#cto-alerts"]
    D --> E
```

- **SLA Breach Radar:** Overdue pull requests are pushed as interactive Slack Block Kit cards featuring PR title, author, branch, days overdue, and a one-click *"Review on GitHub"* action button.
- **Automated Morning PDF Broadcast:** Every morning after 08:00 report synthesis, the compiled PDF is automatically uploaded via Slack's modern 3-step external upload workflow (`files.getUploadURLExternal` → direct binary storage → `files.completeUploadExternal`), including an executive bullet summary.
- **Dedicated Bot Scopes:** Utilizes permanent Bot User OAuth Token (`xoxb-...`) requiring `chat:write`, `files:write`, `channels:read`.
- **Scheduled & On-Demand:** Triggered automatically via Celery Beat (`slack.check_sla_breaches` every 30m, daily report task at 08:00) or on-demand via REST endpoints (`POST /api/slack/notify-overdue`, `POST /api/slack/upload-latest-report`).
- Files: `app/services/slack_service.py` · `app/api/routes.py` (`/api/slack/*`) · `app/services/celery_app.py`

---

### 11 · 🧪 Eval Lab — Torture Tests + MLflow

**Prove there's no hallucination — with numbers, not vibes.** One button queues a background run of **~122 questions** (24 curated adversarial traps + ~100 generated from live DB + synthetic fixtures): counts, follow-ups, false premises, future dates, exact-username traps, language discipline. Every reply is scored and everything lands in MLflow.

```mermaid
flowchart LR
    A["🧪 Run Full Eval<br/>judge ON/OFF toggle"] --> B["Celery task<br/>evals.run_full"]
    B --> C["122 questions<br/>concurrency 3<br/>fresh session each"]
    C --> D["scores: grounding<br/>faithfulness · exact<br/>language · latency"]
    D --> E["📊 MLflow<br/>params + metrics<br/>+ results.json"]
```

#### 📊 Empirical Benchmark Results (122 Torture Questions)

The table below documents the empirical evaluation results tracked in MLflow (`f3ddde2c` and `25360aa6`), comparing identical torture suites with the LLM-as-a-Judge gate enabled versus bypassed:

| Benchmark Metric | 🛡️ Judge ON (`eval-judge-on`) | ⚡ Judge OFF (`eval-judge-off`) | Delta / Architectural Impact |
|---|:---:|:---:|---|
| **Run Status** | `FINISHED` | `FINISHED` | Both suites executed 100% of the torture questions to completion |
| **Questions Evaluated (`QS`)** | **122** | **122** | Identical dataset: adversarial traps + real SQL questions + counterfactuals |
| **Correctness Rate (`CORRECT`)** | **97%** | **99%** | Factual precision vs live ground truth database records |
| **Hallucination Rate (`HALLUC.`)** | **0%** 🎯 | **0%** 🎯 | **Zero hallucination across the board.** The agent refuses to fabricate nonexistent PRs |
| **Faithfulness Score (`FAITHFUL.`)** | **98%** 🔥 | **90%** | **+8.0% Faithfulness Boost** — claims are strictly grounded in retrieved tool outputs |
| **Average Latency (`AVG LAT.`)** | `6.4s` | `3.3s` | Includes dual-pass pipeline (actor generation + independent judge audit) |
| **P95 Latency (`P95`)** | `9.7s` | `5.4s` | P95 latency boundary under complex database queries + judge verification |
| **Average TTFT (`AVG TTFT`)** | `4.35s` | `2.9s` | Time to First Token before output stream begins |
| **SSE Streaming** | `OFF` | `OFF` | Baseline non-streaming measurements |
| **Grounding Gate Status** | **ACTIVE (`ON`)** | **BYPASSED (`OFF`)** | Evaluates response against tool outputs before serving the user |

> **Key Takeaway:** Turning the Judge **ON** boosts Faithfulness from **90% to 98%** (+8%), while maintaining a **0% Hallucination rate**. The ~3.1s latency overhead reflects the asynchronous second-pass audit that guarantees enterprise-grade factual reliability for engineering leadership.

- **Metrics (no deepeval package, by design):** `faithfulness` (judge model vs tool observations — the core hallucination metric) · `grounding` (free deterministic PR-reference gate) · `exact` (char-exact names/numbers) · `language` · `relevancy` · `avg/p95 latency`. Contextual recall/precision deliberately excluded (RAG-retrieval metrics — our retrieval is SQL).
- **Fail is split in two:** `fail_fabrication_rate` (failed AND ungrounded — invented refs, typos, claims with no evidence: the number the CTO actually cares about) vs `fail_quality_rate` (failed BUT grounded — wrong count, indirect answer, language slip: strict-checker territory, not hallucination).
- **Judge ON vs OFF:** run twice with the checkbox, compare `fail_rate` + `faithfulness_avg` side by side in the MLflow UI — that's the experiment that proves the gate's worth.
- **Live progress card:** the UI shows "4 من 62" with a bar while running (`GET /api/eval/progress/{task_id}`); the total follows your Max-questions choice automatically.
- **Latency engineering:** question groups run concurrently (`EVAL_MAX_CONCURRENCY=3`); faithfulness LLM calls are skipped where the outcome is logically forced (rejected→0, refusals→1). Full run ≈ 8–12 min instead of ~30.
- **Judge hardening:** empty judge responses retry, then fall back to Qwen (`JUDGE_RETRIES`, `JUDGE_FALLBACK_MODEL`) — the 28 silent empties from the first big run can't recur silently.
- **Delete runs:** ✕ per row (`DELETE /api/eval/runs/{id}`) soft-deletes from MLflow.
- **Synthetic fixtures:** `eval_fixtures` table (migration `0006`, 32 clearly-fake rows) so generated questions never depend on prod data volume.
- **View it:** `pip install mlflow`, then from the repo root: `mlflow ui --backend-store-uri sqlite:///./mlruns/mlflow.db --port 5000` → http://localhost:5000.
- Files: `app/services/eval_service.py` · `app/models/eval_fixture_model.py` · `app/api/routes.py` (`/api/eval/*`) · `app/services/celery_app.py` (`evals.run_full`) · migration `0006_eval_fixtures.py`

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
        BED["Bedrock Mantle<br/>GPT-OSS-120B (primary)"]
        GROQ["Groq<br/>gpt-oss-20b → 120b (fallback)"]
        JEV["TypeSafe JEV<br/>impact + urgency 1-10"]
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
| `cto-copilot-mysql` | `mysql:8.0` | `3307→3306` | System of record (PRs, engineers, chat, reports, auth, emails) |
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
| 🛡️ Judge | `openai.gpt-oss-20b` | Bedrock Mantle OpenAI client | Pre-delivery anti-hallucination review on chat replies |

Hyperparameters: `LLM_TEMPERATURE=0.2` · `LLM_MAX_TOKENS=1024` — deterministic, executive-dense output without reasoning overhead.

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
    EMAILS {
        int id PK
        string message_id UK
        string sender
        string subject
        datetime sent_at
        text summary_text
        float urgency_score
        string urgency_tier
        bool is_hidden
    }
    EVAL_FIXTURES {
        int id PK
        string kind
        string ref_name UK
        string title
        string owner
        string state
        datetime event_date
        float score
        string tier
    }
```

- Migrations: `0001_initial_two_tables` (PRs + engineers) · `0002_daily_reports` · `0003_auth_state` · `0004_emails` · `0005_email_dismiss` · `0006_eval_fixtures`. App container runs `alembic upgrade head` on startup — plain `docker compose up` keeps schema current.
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

### Emails

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/emails?limit=30` | Triaged emails, newest first |
| `POST` | `/api/emails/sync` | Run one inbox poll now (503 if mailbox unreachable) |
| `DELETE` | `/api/emails/{id}` | Dismiss from the list (soft-hide, never resurrected) |

### Eval Lab

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/eval/run` | Queue a torture run (`{use_judge, max_questions?}`) → `{task_id}` |
| `GET` | `/api/eval/runs/{task_id}` | Celery task state (PENDING / SUCCESS / FAILURE + summary) |
| `GET` | `/api/eval/progress/{task_id}` | Live `{current, total}` for the "X من Y" card |
| `GET` | `/api/eval/recent?limit=10` | Last MLflow runs for the dashboard table |
| `DELETE` | `/api/eval/runs/{run_id}` | Soft-delete an MLflow run |

---

## ⚙️ Configuration — Comprehensive Environment Variable Reference

CTO Watch is configured via environment variables. To get started, duplicate the template file and populate your credentials:

```bash
cp .env.example .env
```

> [!WARNING]
> **Never commit your `.env` file to version control.** It contains highly sensitive production credentials, API tokens, S3 secret keys, and database passwords.

Every variable available in [`.env.example`](file:///d:/CTO_MULTI_AGENT/.env.example) is documented below by functional category, detailing its type, default value, and exact architectural role.

---

### 1 · GitHub Integration
Controls synchronization with GitHub repositories, polling cadences, and Pull Request staleness criteria.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `GITHUB_TOKEN` | `your_github_token_here` | String | Personal Access Token (PAT) or fine-grained GitHub token with `repo` read/write permissions. Used by `GitHubCollector` to fetch commits, PRs, diffs, reviews, and CI status. |
| `GITHUB_REPO` | `SeifMahmoud63/CTO-Copilot` | String | Target repository identifier in `owner/repo` format audited by the multi-agent system. |
| `GITHUB_API_URL` | `https://api.github.com` | URL | Base REST API endpoint for GitHub. Change to an enterprise URL (e.g. `https://github.corp.internal/api/v3`) for GitHub Enterprise Server. |
| `GITHUB_POLL_INTERVAL_SECONDS` | `30` | Integer | Background polling interval in seconds. Defines how frequently the daemon queries GitHub for newly opened or updated PRs. |
| `PR_STALE_THRESHOLD_DAYS` | `5` | Integer | Inactivity threshold in days. Open PRs without code pushes or review activity exceeding this limit are flagged as stale in executive briefings and SLA alerts. |

---

### 2 · AWS Bedrock / Mantle API (Primary Summarization & Inference)
Powers the primary summarization pipelines, PR risk analysis, and executive report authoring.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `BEDROCK_API_KEY` | `your_bedrock_api_key_here` | String | Bearer authorization API key used to authenticate with Bedrock Mantle / AWS gateway endpoints. |
| `BEDROCK_BASE_URL` | `https://bedrock-mantle.us-west-2.api.aws/openai/v1` | URL | OpenAI-compatible endpoint URL for routing inference requests through AWS Bedrock. |
| `BEDROCK_BASE_URL_QWEN` | `https://bedrock-mantle.us-west-2.api.aws/v1` | URL | Dedicated base URL for routing Qwen foundation models to prevent route collision with OpenAI proxy endpoints. |
| `BEDROCK_VISION_MODEL` | `us.amazon.nova-pro-v1:0` | String | Multimodal vision model identifier used for analyzing architectural diagrams, UI diff screenshots, and visual assets. |
| `BEDROCK_MODEL` | `qwen.qwen3-32b` | String | Primary foundation model identifier for automated PR code reviews, technical risk scoring, and daily reports. |
| `AWS_ACCESS_KEY_ID` | `your_aws_access_key` | String | Standard AWS IAM access key ID for native AWS SDK / boto3 sessions. |
| `AWS_SECRET_ACCESS_KEY` | `your_aws_secret_key` | String | Standard AWS IAM secret access key matching `AWS_ACCESS_KEY_ID`. |
| `AWS_REGION` | `us-west-2` | String | Primary AWS region where Bedrock foundation models are provisioned. |
| `AWS_DEFAULT_REGION` | `us-west-2` | String | Fallback AWS region variable for underlying AWS CLI and SDK client libraries. |

---

### 3 · JEV Decision Engine (Impact & Urgency Scoring)
Assigns quantitative impact and business urgency scores (1.0 to 10.0) to every Pull Request.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `JEV_API_KEY` | `your_jev_api_key_here` | String | Secret API key for authenticating with the TypeSafe JEV SystemOne decision engine. |
| `JEV_API_URL` | `https://api.typesafe.ai/v1/systemone` | URL | Target REST API endpoint for the JEV decision scoring engine. |
| `JEV_MODEL` | `jev-latest` | String | Model release tag for JEV scoring. If `JEV_API_KEY` is omitted or invalid, the engine gracefully degrades to a neutral score of `5.0`. |

---

### 4 · Google Gemini (Chatbot Actor)
Drives the conversational CTO Copilot agent when configured as the primary chat actor.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `GEMINI_API_KEY` | `your_gemini_api_key_here` | String | Google AI Studio API key used to execute multi-turn conversational tool calling. |
| `GEMINI_CHAT_MODEL` | `gemini-3.1-pro-preview` | String | Active Gemini model ID for chat interactions (alternatives include `gemini-3.8-flash`). |
| `CHAT_PROVIDER` | `gemini` | String | Chat actor provider selector (`gemini` or `bedrock`). Allows running the chatbot actor on Gemini while keeping the Judge and summaries on Bedrock. |

---

### 5 · Groq Cloud (High-Speed Fallback Chain & Judge Backup)
Provides ultra-low-latency LPU failover execution if primary providers suffer rate limits (429) or outages (5xx).

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `GROQ_API_KEY` | `your_groq_api_key_here` | String | Groq Cloud authorization API key. |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | URL | OpenAI-compatible endpoint base URL for Groq LPU inference. |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | String | Primary high-speed fallback model automatically engaged if primary Bedrock/Gemini requests fail. |
| `GROQ_BACKUP_MODEL` | `openai/gpt-oss-120b` | String | Secondary high-capacity fallback model in the multi-tier provider resilience chain. |

---

### 6 · LLM Hyperparameters & Reasoning
Governs output determinism, response length boundaries, and reasoning depth across all models.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `LLM_TEMPERATURE` | `0.2` | Float | Sampling temperature. Kept strictly low (`0.2`) to guarantee factual consistency, high determinism, and reliable tool call argument parsing. |
| `LLM_MAX_TOKENS` | `1024` | Integer | Hard token output ceiling per generation. Prevents verbose runaway answers and maintains concise executive briefings. |
| `LLM_REASONING_EFFORT` | `high` | String | Reasoning effort level for reasoning-capable models (`low`, `medium`, `high`, or empty string). Setting to `low` achieves ~3x faster latency while maintaining factual rigor. |

---

### 7 · Circuit Breaker (Resilience Governor)
Protects against cascading external API failures and runaway billing loops.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `CIRCUIT_BREAKER_COOLDOWN_SECONDS` | `1800` | Integer | Cooldown duration in seconds (30 minutes) that the circuit breaker remains in `OPEN` state after repeated provider failures before testing recovery. |
| `CIRCUIT_BREAKER_PROBE_PROMPT` | `ping` | String | Minimalist synthetic health probe prompt sent during the `HALF-OPEN` state to verify upstream provider recovery before re-opening traffic. |

---

### 8 · Application Server
Configures the FastAPI HTTP application runtime and static file serving.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `APP_HOST` | `0.0.0.0` | IP | Host interface binding. `0.0.0.0` binds to all network interfaces to permit Docker container ingress. |
| `APP_PORT` | `8000` | Integer | Internal HTTP server port listened on by Uvicorn. |
| `STATIC_DIR` | `web` | Path | Relative directory path containing the built frontend single-page application (HTML, CSS, JS bundles). |

---

### 9 · MySQL Database
Configures relational storage for PR metadata, automated reviews, triage audits, and chat history.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `MYSQL_HOST` | `mysql` | String | Database hostname (`mysql` inside the Docker Compose network; `127.0.0.1` when running directly on the host machine). |
| `MYSQL_PORT` | `3306` | Integer | MySQL service port inside Docker (`3306`; host exposed port is mapped to `3307` to prevent collisions with existing host MySQL services). |
| `MYSQL_USER` | `cto_user` | String | Primary application database user account. |
| `MYSQL_PASSWORD` | `cto_password_2026` | String | Password for the application database user. |
| `MYSQL_DATABASE` | `cto_copilot_db` | String | Target database schema name housing all CTO Watch business tables. |
| `MYSQL_ROOT_PASSWORD` | `cto_root_password_2026` | String | Administrative MySQL root password used for database container provisioning. |
| `DATABASE_URL` | *(empty)* | Connection URI | Full SQLAlchemy connection URI (e.g. `mysql+pymysql://cto_user:cto_password_2026@mysql:3306/cto_copilot_db`). If left blank, it is automatically constructed from the individual `MYSQL_*` parameters. |

---

### 10 · Chatbot Agent & Memory
Controls conversational sliding context windows, pronoun resolution rewrite depth, and token streaming.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `CHAT_MEMORY_WINDOW_SIZE` | `10` | Integer | Maximum number of preceding conversational dialogue turns retained in the active context window. |
| `CHAT_QUERY_REWRITE_WINDOW_SIZE` | `2` | Integer | Number of prior conversational turns passed to the query rewriter to de-reference ambiguous pronouns (e.g., "What about the second PR?") into self-contained SQL questions. |
| `CHAT_SSE_ENABLED` | `false` | Boolean | Default boot switch for Server-Sent Events (SSE) token streaming. Can also be dynamically toggled at runtime via `POST /api/chat/sse`. |

---

### 11 · Celery Distributed Queue & Redis
Powers background worker task distribution for PDF generation, GitHub polling, and Eval Lab benchmarks.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | URL | Redis connection URL serving as the message broker for Celery tasks. |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` | URL | Redis connection URL utilized to store Celery task completion results and state transitions. |

---

### 12 · Daily CTO Report (Celery Beat Scheduler)
Controls the automated cron schedule, format, and localization for daily executive briefings.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `REPORT_TIMEZONE` | `Africa/Cairo` | String | IANA timezone identifier governing the exact execution schedule for the daily report task. |
| `REPORT_HOUR` | `8` | Integer | Scheduled hour of execution (0–23 in 24h format; `8` triggers at 08:00 AM local time). |
| `REPORT_MINUTE` | `0` | Integer | Scheduled minute of execution (0–59). |
| `REPORTS_DIR` | `reports` | Path | Local working directory where generated daily PDF briefings are staged before being uploaded to MinIO S3. |
| `REPORT_LANGUAGE` | `English` | String | Natural language used to compose executive briefings. Kept strictly in English to ensure pristine left-to-right (LTR) PDF typography. |

---

### 13 · Deepgram Live Voice Agent
Enables real-time, low-latency duplex voice conversations with CTO Copilot over WebSockets.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `DEEPGRAM_API_KEY` | `your_deepgram_api_key_here` | String | Deepgram API key enabling speech-to-text transcription and text-to-speech audio synthesis. |
| `DEEPGRAM_AGENT_MODEL` | `nova-3` | String | Speech recognition model identifier delivering high-accuracy real-time transcription. |
| `DEEPGRAM_VOICE_MODEL` | `aura-asteria-en` | String | Natural neural voice persona synthesizer identifier. |
| `DEEPGRAM_AGENT_URL` | `wss://agent.deepgram.com/v1/agent/converse` | URL | Full WebSocket gateway endpoint for real-time bi-directional voice streaming. |

---

### 14 · Access Gate & Authentication (TOTP / MFA)
Secures the executive web portal and REST endpoints against unauthorized access.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `CTO_PASSWORD` | `change_me_to_a_strong_password` | String | Shared master password required to access the dashboard and APIs. **Fails closed** if left blank. |
| `SESSION_SECRET` | `generate_with_python_secrets...` | String | High-entropy cryptographic secret key used to sign HMAC session tokens and cookies. Generate via `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |
| `SESSION_MAX_AGE_HOURS` | `12` | Integer | Standard session validity duration in hours before re-authentication is mandatory. |
| `REMEMBER_ME_DAYS` | `7` | Integer | Extended session lifespan in days when the "Remember Me" checkbox is enabled during login. |
| `TOTP_ISSUER` | `CTO-Copilot` | String | Organization issuer label displayed in authenticator applications (e.g., Google Authenticator, 1Password) upon scanning the QR code. |
| `AUTH_MAX_ATTEMPTS` | `3` | Integer | Maximum consecutive invalid login attempts allowed per IP address before triggering an automatic lockout. |
| `AUTH_LOCKOUT_SECONDS` | `1800` | Integer | Lockout penalty window in seconds (30 minutes) enforced after exceeding `AUTH_MAX_ATTEMPTS`. |

---

### 15 · LLM-as-a-Judge (Grounding Gate)
Prevents hallucinated claims by performing an independent second-pass verification against live SQL tool outputs.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `JUDGE_ENABLED` | `true` | Boolean | Master switch for the Grounding Gate. When `true`, every chatbot reply is independently audited against retrieved tool outputs before reaching the user. |
| `JUDGE_MODEL` | `openai.gpt-oss-20b` | String | Primary Bedrock model identifier executing the factual grounding and faithfulness audit. |
| `JUDGE_MAX_TOKENS` | `1024` | Integer | Maximum token budget allocated for the judge verification decision. |
| `JUDGE_RETRIES` | `1` | Integer | Number of immediate retry attempts executed if the judge model returns an empty or unparseable response. |
| `JUDGE_FALLBACK_MODEL` | `openai/gpt-oss-20b` | String | Backup judge model identifier routed via Groq. Hosted on independent infrastructure so that an AWS outage does not disable the grounding audit. |

---

### 16 · Eval Lab Execution
Controls execution throughput and resource allocation during empirical torture testing.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `EVAL_MAX_CONCURRENCY` | `3` | Integer | Maximum number of parallel question suites executed simultaneously during Eval Lab benchmark runs (`1` enforces purely sequential execution). |

---

### 17 · Email Triage (Read-Only IMAP)
Autonomously monitors engineering and security email threads, categorizing urgency and filing actionable tickets.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `EMAIL_ENABLED` | `false` | Boolean | Master switch enabling or disabling background email inbox triage. |
| `EMAIL_IMAP_HOST` | `imap.gmail.com` | Hostname | IMAP server hostname used to retrieve incoming messages. |
| `EMAIL_IMAP_PORT` | `993` | Integer | Secure IMAP port (SSL/TLS). |
| `EMAIL_ADDRESS` | *(empty)* | Email | Dedicated inbox email address audited by the agent. |
| `EMAIL_PASSWORD` | *(empty)* | Secret | Dedicated App Password for the mailbox (never use your primary account password). |
| `EMAIL_MAILBOX` | `INBOX` | String | Target remote mailbox folder scanned during triage cycles. |
| `EMAIL_UNREAD_ONLY` | `true` | Boolean | When `true`, only unread messages are processed and subsequently marked as reviewed. |
| `EMAIL_POLL_INTERVAL_MINUTES` | `3` | Integer | Background polling cadence in minutes between mailbox inspections. |
| `EMAIL_MAX_BODY_CHARS` | `4000` | Integer | Character truncation limit per email body to prevent context window saturation from large signatures or log dumps. |

---

### 18 · Slack Bot Integration
Delivers proactive SLA breach warnings and automated daily PDF briefing distribution to Slack.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `SLACK_ENABLED` | `false` | Boolean | Master switch enabling or disabling real-time Slack notifications. |
| `SLACK_BOT_TOKEN` | `xoxb-your-slack-bot-token` | String | Slack Bot User OAuth Token with `chat:write` and `files:write` scopes. |
| `SLACK_CHANNEL_ID` | `C0123456789` | String | Designated Slack channel ID where alerts, critical PR warnings, and daily PDFs are posted. |

---

### 19 · MinIO S3 Object Storage
Provides enterprise S3-compatible cloud object storage for PDF reports, MLflow experiment artifacts, and benchmark progress data.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `MINIO_ENDPOINT` | `http://localhost:9000` | URL | S3 API endpoint URL (`http://localhost:9000` on host; `http://minio:9000` inside Docker Compose). MinIO Web UI console runs at `http://localhost:9001`. |
| `MINIO_ACCESS_KEY` | `cto-minio-admin` | String | Administrative access key (username) for MinIO S3 storage. |
| `MINIO_SECRET_KEY` | `change_me_to_a_very_strong_38char...` | String | High-entropy secret key for MinIO S3 authentication. |
| `MINIO_BUCKET_REPORTS` | `cto-reports` | String | S3 bucket name designated for permanent storage of daily PDF and HTML executive reports. |
| `MINIO_BUCKET_MLFLOW` | `mlflow-artifacts` | String | S3 bucket name holding MLflow evaluation benchmark artifacts, models, and run outputs. |
| `MINIO_BUCKET_PROGRESS` | `eval-progress` | String | S3 bucket name holding real-time evaluation benchmark task progress counters. |
| `MINIO_SECURE` | `false` | Boolean | Set to `true` when using HTTPS/TLS on the MinIO endpoint, or `false` for standard plaintext HTTP. |

---

### 20 · MLflow Tracking & Artifact Storage
Tracks empirical evaluation runs, LLM grounding metrics, latency distributions, and parameter configurations.

| Variable | Default / Example | Type | Description |
|---|---|:---:|---|
| `MLFLOW_TRACKING_URI` | `mysql+pymysql://cto_user:cto_password_2026@mysql:3306/mlflow_db` | Connection URI | Storage location for MLflow experiment runs and metric timeseries. In Docker Compose, uses dedicated isolated database `mlflow_db`. For quick local dev without Docker, use `sqlite:///./mlruns/mlflow.db`. |
| `MLFLOW_S3_ENDPOINT_URL` | `http://localhost:9000` | URL | S3 API endpoint allowing the MLflow tracking client to upload `results.json` and artifact logs directly to MinIO. |

---

## 🚀 Quick Start — Run in 60 Seconds

```powershell
# 1 · configure (run from the repo root — no hardcoded paths)
Copy-Item .env.example .env
# edit .env → GITHUB_TOKEN, CTO_PASSWORD, SESSION_SECRET (see Gate section), LLM keys

# 2 · launch the whole stack (mysql + redis + app + worker + beat)
docker compose up -d --build

# 3 · open
Start-Process http://localhost:8000/
Start-Process http://localhost:8000/docs
```

macOS / Linux (`bash`) equivalent:

```bash
# run from the repo root
cp .env.example .env
# edit .env, then:
docker compose up -d --build
xdg-open http://localhost:8000/ || open http://localhost:8000/
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
│   │   ├── judge_service.py     # LLM-as-a-Judge grounding gate
│   │   ├── voice_service.py     # Deepgram bridge · read-only SQL tool
│   │   ├── report_service.py    # metrics → AI analysis → PDF (Amiri font)
│   │   ├── email_service.py     # IMAP poll (read-only) · summary · urgency score
│   │   ├── eval_service.py      # torture harness · fixtures · metrics · MLflow
│   │   ├── celery_app.py        # worker + beat schedules (08:00 report · inbox poll)
│   │   ├── db_service.py        # MySQL upserts · engineers rebuild · reports/emails CRUD
│   │   └── auth_service.py      # password+TOTP · Fernet · cookies · rate limit
│   ├── models/                  # pr · engineer · chat · report · auth · email · eval fixtures (SQLAlchemy)
│   ├── schemas/                 # PRItem · DashboardLeaderboardResponse · …
│   └── db/                      # async engine + session factory
├── web/
│   ├── index.html               # 9 views: home/prs/overdue/dashboard/chat/reports/emails/eval/voice
│   ├── app.js                   # fetch · render · chat · voice WS · drawer
│   ├── style.css                # design system (Plus Jakarta Sans)
│   └── login.html               # password → QR → TOTP → remember-me
├── alembic/versions/            # 0001 two-tables · 0002 reports · 0003 auth_state · 0004 emails · 0005 dismiss · 0006 fixtures
├── tests/                       # auth · chat · rewrite · judge · reports · voice · emails · eval · migrations
├── reports/                     # generated daily PDFs (git-ignored artefacts)
├── docs/screenshots/            # ← 13 live captures (see Visual Showcase above)
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
| `test_chat_query_rewrite.py` | LLM follow-up rewriting + rewrite-window plumbing |
| `test_judge.py` | Grounding gate (fabricated-PRs blocked) + verdict parsing + retry/fallback |
| `test_emails.py` | MIME parsing + urgency tiers + DB roundtrip + mocked poll flow |
| `test_eval.py` | Fixture seed determinism + case counts + checkers + MLflow-absent safety + progress + faithfulness skips + run delete |
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
