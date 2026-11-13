# 🇰🇷 KOREA-LIFE

A **two-sided** multilingual platform connecting foreign residents in South Korea
with the institutions that serve them.

- **Residents** navigate official services, get answers grounded **only** in
  official sources, and track life's deadlines (health insurance, residence card
  and passport expiry, rent, tuition, employment contracts, taxes).
- **Institutions** — universities, employers, support organizations — use
  **KOREA-LIFE Connect** to publish verified information (which the assistant can
  cite), receive inquiries that need a human, and view anonymized question trends.

Built with **Python + Streamlit + SQLite + the Anthropic Claude API**.

> **Important:** KOREA-LIFE is a navigation and reminder aid — **not** legal,
> immigration, labor, healthcare, or financial advice. It never states visa
> rules, eligibility, requirements, fees, or legal deadlines. Always confirm
> specifics with the official source or helpline.

---

## ✨ Features

**Resident side — four pages + the Life Manager module**

1. **Home dashboard** — onboarding, reminder metrics, the notification center, a
   "grounded in official sources" trust band, and Today / Upcoming / Overdue /
   Completed at a glance.
2. **AI Copilot** — ask questions in your language; answers are generated from
   retrieved official-source records (and verified organization info) and returned
   as a structured, cited result. Turn action steps into tracked reminders, or
   route the question to a relevant organization for human help.
3. **My Life Plan** — the full list of everything you track, with status,
   countdowns and filters.
4. **Trusted Services** — the curated directory of official sources, plus a
   language-assistance tool that prepares Korean scripts with translations.
5. **Life Manager (core module)** — create one-time and recurring reminders
   manually or from a pasted notice (with confirmation), manage recurrence and
   multiple advance-reminder offsets (e.g. 60/30/7 days before a document
   expires), and work the Today / Upcoming / Overdue / Completed dashboard with
   mark-paid, snooze, edit and delete.

**Institutional side — KOREA-LIFE Connect (two pages)**

6. **KOREA-LIFE Connect** — the institutional landing page explaining the
   two-sided model and listing participating (demo) organizations.
7. **Institution Console** — the organization dashboard with four tabs:
   - **Profile** — manage the organization's details.
   - **Published info** — publish/edit verified procedures, FAQs, and
     requirements. Published items are **retrieved and cited by the AI assistant**
     when relevant to a resident's question.
   - **Inquiries** — an inbox of questions routed from residents via the
     assistant; set status and reply. No passport/ID or card numbers are collected.
   - **Insights** — privacy-protected aggregate trends (top topics, by language,
     by city, volume over time). No raw question text, no personal data.

> **How the two sides connect:** organizations *publish* → the assistant
> *surfaces and cites* their verified info → residents can *route* a question to
> the organization → the organization manages inquiries and sees *anonymized*
> trends. All organization data is **synthetic demo data**; there are no real
> government integrations and no real partnerships.

**Grounded & safe AI**
- Retrieval over a hand-curated JSON knowledge base of **official** sources:
  HiKorea, Ministry of Justice 1345, Government24 (Foreigners), NHIS foreigner
  guidance, MOEL 1350, and the Seoul Foreign Resident Portal.
- Claude is used **only** with retrieved source evidence + your profile, and must
  return a strict JSON structure (`answer`, `applicability`,
  `clarifying_questions`, `action_steps`, `source_ids`, `uncertainty`,
  `escalation_contact`, `korean_script`, `needs_official_verification`).
- Cites **only** source IDs actually retrieved. If the sources don't support an
  answer, it says so and points you to an official contact.
- High-stakes immigration, legal, labor, healthcare and financial queries are
  flagged for official verification.

**Robust offline fallback**
- With **no `ANTHROPIC_API_KEY`**, the app runs fully in a deterministic demo
  mode: answers are composed from the local official-source records and clearly
  labeled as offline. The app never breaks because a key is missing.

**Privacy by design**
- Never asks for passport or Residence Card **numbers**, bank credentials, or
  other unnecessary sensitive identifiers. The residence *category* field (e.g.
  `D-2`) is optional and is a label only.
- API secrets come from environment variables — **never hardcoded**.

---

## 🚀 Installation & launch (exact commands)

Requires **Python 3.9+**.

```bash
# 1. Go to the project folder
cd korea-life

# 2. (Recommended) create and activate a virtual environment
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) configure your API key for live AI answers
cp .env.example .env
#   then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
#   Leave it blank to run in offline demo (fallback) mode.

# 5. Run the app
streamlit run app.py
```

The app opens at **http://localhost:8501**. On first launch, either complete the
short onboarding form or click **“Load synthetic demo profile”** to explore
immediately.

### Run the tests

```bash
python -m tests.test_core
```

---

## 🔑 Configuration (environment variables)

Set these in `.env` (copied from `.env.example`) or in your shell. Secrets are
read from the environment only.

| Variable            | Required | Default            | Purpose                                             |
|---------------------|----------|--------------------|-----------------------------------------------------|
| `ANTHROPIC_API_KEY` | No       | *(empty)*          | Enables live Claude answers. Blank → fallback mode. |
| `ANTHROPIC_MODEL`   | No       | `claude-sonnet-4-5`| Override the Claude model used.                     |
| `KOREA_LIFE_DB`     | No       | `korea_life.db`    | Override the SQLite database path.                  |

---

## 🗂️ Project structure

```
korea-life/
├── app.py                     # Home dashboard + onboarding (Streamlit entry)
├── pages/
│   ├── 1_AI_Copilot.py        # Source-grounded Q&A + save action steps
│   ├── 2_My_Life_Plan.py      # Full tracked-items view with countdowns
│   ├── 3_Life_Manager.py      # Core reminder module (create/notice/manage)
│   ├── 4_Trusted_Services.py  # Official directory + language assistance
│   ├── 5_KOREA_LIFE_Connect.py# Institutional landing (two-sided model)
│   └── 6_Institution_Console.py # Org dashboard: profile/publish/inquiries/insights
├── korealife/                 # Core logic (importable, unit-tested)
│   ├── config.py              # Paths + env-driven settings (secrets from env)
│   ├── database.py            # SQLite persistence (profile + reminders)
│   ├── knowledge.py           # Retrieval over the curated knowledge base
│   ├── ai.py                  # Claude client + deterministic fallback
│   ├── reminders.py           # Life Manager engine (status/recurrence/offsets)
│   ├── extract.py             # Date/amount extraction from notices (confirmed)
│   ├── connect.py             # KOREA-LIFE Connect: orgs, resources, inquiries, trends
│   ├── i18n.py                # UI translation dictionary
│   └── ui.py                  # Shared Streamlit UI helpers + visual system
├── data/
│   ├── knowledge_base.json    # Curated official-source records
│   ├── demo_profile.json      # SYNTHETIC demo profile
│   └── demo_questions.json    # SYNTHETIC demo questions
├── tests/test_core.py         # Core logic tests (isolated temp DB)
├── requirements.txt
├── .env.example
└── .streamlit/config.toml
```

---

## 🧠 How the AI stays grounded

1. Your question + profile go to a simple keyword/geography retriever over
   `data/knowledge_base.json`.
2. Only the retrieved records are passed to Claude as the *sole* evidence, with a
   system prompt forbidding outside knowledge and invented rules.
3. Claude returns strict JSON. The app then **enforces** invariants: it strips any
   cited source ID that wasn't retrieved, and forces the verification flag on for
   high-stakes topics.
4. If no source matches, the app says so and routes you to an official contact —
   it does not guess.

Each knowledge-base record has: `id`, `title`, `issuer`, `topic`, `geography`,
`url`, `verified_summary`, `excerpts`, `languages`, `escalation_contact`, and
`last_checked`. Summaries are deliberately high-level: they describe what each
official source covers and how to reach it, not the rules themselves.

---

## ⏰ Reminders, statuses & recurrence

- **Categories:** health insurance, residence card, passport, visa, rent,
  utilities, tuition, employment contract, subscription, appointment, tax, task,
  other.
- **Recurrence:** none, weekly, monthly, yearly, or custom (every N days).
  Completing a recurring reminder automatically generates the next occurrence.
- **Advance reminders (offsets):** choose multiple, e.g. **60 / 30 / 7** days
  before a document expires. Health-insurance reminders use **your** actual bill
  due date and can recur monthly.
- **Derived status:** Overdue, Due today, Due soon, Upcoming, Completed —
  recomputed on every app open/refresh.
- Saved dates are labeled **personal reminders**, *not* statutory deadlines,
  unless you explicitly mark one as verified from an official source.
- **From a notice:** paste a bill/notice; the app *suggests* dates and amounts it
  finds — nothing is saved until **you confirm**. It never infers statutory
  deadlines or universal due dates.

---

## 🔔 About notifications (please read)

This prototype includes an **in-app notification center** and a reminder-check
routine that runs **every time the app opens or refreshes**. That is the full
extent of the notifications implemented here.

**It does NOT send external notifications** (email, SMS, or push). Real external
alerts require a **continuously running scheduler or notification service** —
for example a cron job, `APScheduler`, a cloud scheduled task, or a push/email
provider — that runs independently of the Streamlit session. Wiring that up is
intentionally out of scope for this one-day prototype, and the app does not
pretend those channels are active.

---

## ⚠️ Scope & honesty

By design, KOREA-LIFE does **not**:
- integrate with banking, government logins, or government APIs;
- perform automated submissions on your behalf;
- send push/email/SMS notifications;
- display fake “live” statistics or pretend demo data is real.

All demo data is clearly labeled **synthetic**. For authoritative, case-specific
answers, use the official contacts in **Trusted Services** — most importantly the
**1345 Immigration Contact Center** for immigration questions.
