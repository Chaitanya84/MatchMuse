# MatchMuse — Complete Project Documentation

> **Intelligent Resume Matching Tool** · Powered by Claude Opus 4.6 via GenAI-Nexus (AWS Bedrock)  
> Created by Chaitanya Priya · Last updated: June 2026

---

## Table of Contents

1. [Project Summary](#1-project-summary)
2. [Quick Start](#2-quick-start)
3. [System Architecture](#3-system-architecture)
4. [File Structure](#4-file-structure)
5. [Multilingual Support](#5-multilingual-support)
6. [Authentication & Login](#6-authentication--login)
7. [Deployment on Render](#7-deployment-on-render)
8. [Testing Guide](#8-testing-guide)
9. [Debug Strategies](#9-debug-strategies)
10. [Migration Notes (Flask → Streamlit)](#10-migration-notes-flask--streamlit)
11. [Environment Variables Reference](#11-environment-variables-reference)

---

## 1. Project Summary

MatchMuse is a production-ready, AI-powered recruitment tool that:

- **Ranks resumes** against a job description using Claude Opus 4.6 — scoring candidates on keyword match, employment duration, job stability, and recency of experience.
- **Generates 5 personalised interview questions** per top candidate based on their actual resume content.
- **Supports multilingual documents** — automatically detects language and translates to English before analysis using Claude Opus 4.6.
- **Produces downloadable PDF reports** for each candidate directly from the Streamlit UI.
- **Requires login** — username and password are enforced via environment variables before any functionality is accessible.

### Key Technologies

| Layer | Technology |
|-------|-----------|
| Frontend/UI | Streamlit 1.32+ |
| AI / LLM | Claude Opus 4.6 via GenAI-Nexus (AWS Bedrock boto3) |
| PDF parsing | PyPDF2 3.0 |
| Word parsing | python-docx 0.8 |
| Language detection | langdetect 1.0.9 |
| PDF generation | fpdf2 2.7.9 |
| Environment config | python-dotenv |
| Deployment | Render (managed PaaS) |

---

## 2. Quick Start

### Prerequisites

- Python 3.8+
- A valid **NEXUS_API_KEY** from the GenAI-Nexus (AWS Bedrock) portal
- Login credentials to set as environment variables

### Local Setup (Linux / macOS)

```bash
# 1. Enter project directory
cd /home/prichai/MatchMuse

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — fill in NEXUS_API_KEY, MATCHMUSE_USERNAME, MATCHMUSE_PASSWORD

# 5. Run the app
streamlit run app_streamlit.py
```

Open your browser at **http://localhost:8501**, sign in with your credentials, and start analysing.

### Local Setup (Windows)

```bat
cd MatchMuse
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
REM Edit .env with Notepad
streamlit run app_streamlit.py
```

### Usage Workflow

1. **Sign in** with your username and password.
2. **Paste a job description** (minimum 50 characters).
3. **Upload resumes** — drag & drop or browse (PDF, DOCX, DOC, TXT; up to 10 files, 10 MB each).
4. Optionally enable **Language Detection** to preview detected languages before analysis.
5. Click **"Analyze Resumes"** — wait 30–90 seconds for AI analysis.
6. Review **ranked candidates**, their scores, and AI-generated interview questions.
7. **Download PDF** for any candidate report.
8. **Logout** via the sidebar when done.

---

## 3. System Architecture

```
┌────────────────────────────────────────────────────────┐
│                  Browser / Streamlit UI                │
│  Login Page → Job Description + Resume Upload          │
│  Results: Rankings | Questions | PDF Download          │
└───────────────────────────┬────────────────────────────┘
                            │  Streamlit session state
                            ▼
┌────────────────────────────────────────────────────────┐
│             app_streamlit.py  (Main App)               │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ Auth Guard   │  │LanguageHandler│ │RankingEngine│  │
│  │ (env-var     │  │ detect lang  │ │ keyword     │  │
│  │  credentials)│  │ translate    │ │ extraction  │  │
│  └──────────────┘  └──────────────┘ └─────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                   │
│  │ResumeProcessor│ │ generate_pdf │                   │
│  │ PDF/DOCX/TXT │ │ (fpdf2)      │                   │
│  └──────────────┘  └──────────────┘                   │
└───────────────────────────┬────────────────────────────┘
                            │  boto3  (AWS Bedrock)
                            ▼
┌────────────────────────────────────────────────────────┐
│              nexus_client.py  (API Layer)               │
│  • rank_resumes()          — ranking prompt             │
│  • generate_questions()    — interview Q prompt         │
│  • translate_text()        — translation prompt         │
│  • translate_report_content() — batch translate         │
│  Auth: AWS_BEARER_TOKEN_BEDROCK = NEXUS_API_KEY         │
│  Model: claude-opus-4.6                                 │
│  Endpoint: genai-nexus.api.corpinter.net                │
└────────────────────────────────────────────────────────┘
```

### Data Flow

```
Resume Files (PDF/DOCX/TXT)
       │
       ▼
ResumeProcessor.extract_text()
       │
       ▼
LanguageHandler.detect_language()
       │ (if not English)
       ▼
NexusClient.translate_text()   ← Claude Opus 4.6
       │
       ▼
RankingEngine.extract_keywords(job_description)
       │
       ▼
NexusClient.rank_resumes()     ← Claude Opus 4.6
       │
       ▼
NexusClient.generate_questions() (top 3 candidates)
       │
       ▼
Streamlit Results Page + PDF generation
```

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `app_streamlit.py` | Streamlit UI, auth guard, PDF generation, analysis orchestration |
| `nexus_client.py` | All LLM API calls via boto3 (ranking, questions, translation) |
| `resume_processor.py` | Extract text from PDF, DOCX, TXT; detect candidate name from filename |
| `ranking_engine.py` | Local keyword extraction, keyword-match scoring, employment history parsing |
| `language_handler.py` | Language detection (langdetect) and translation orchestration |
| `app.py` | Legacy Flask REST API backend (kept for reference; not used in production) |

---

## 4. File Structure

```
MatchMuse/
│
├── 🔐 AUTHENTICATION & CONFIG
│   ├── .env.example              ← Template: copy to .env
│   ├── .env                      ← Local secrets (never commit)
│   ├── render.yaml               ← Render deployment manifest
│   └── .streamlit/
│       └── config.toml           ← Streamlit server / theme config
│
├── 🐍 BACKEND (Python)
│   ├── app_streamlit.py          ← Main app (Streamlit, includes auth)
│   ├── nexus_client.py           ← AWS Bedrock / Claude API client
│   ├── ranking_engine.py         ← Local keyword & scoring engine
│   ├── resume_processor.py       ← File parsing (PDF, DOCX, TXT)
│   └── language_handler.py       ← Language detection & translation
│
├── 🌐 LEGACY FLASK (not used in production)
│   ├── app.py                    ← Flask REST API (reference only)
│   ├── templates/index.html      ← Flask HTML template
│   └── static/
│       ├── styles.css            ← CSS styling
│       └── script.js             ← Vanilla JS client
│
├── 📋 SAMPLES
│   └── samples/
│       ├── sample_job_description.txt
│       ├── resume_john_doe.txt
│       ├── resume_sarah_johnson.txt
│       └── resume_michael_chen.txt
│
├── 🧪 TESTING & DEBUGGING
│   ├── test.py                   ← Basic unit tests
│   ├── test_multilingual.py      ← Multilingual tests
│   ├── test_multilingual.sh      ← Shell test runner
│   ├── debug_api.py              ← API connectivity test
│   ├── create_test_data.sh       ← Creates /tmp/resume_test/ fixtures
│   └── verify.sh                 ← Environment verification script
│
├── 📦 DEPENDENCIES
│   └── requirements.txt
│
└── 📚 DOCUMENTATION
    └── doc.md                    ← This file (unified documentation)
```

---

## 5. Multilingual Support

### Overview

MatchMuse automatically handles multilingual job descriptions and resumes. No manual configuration is required.

### Supported Languages (14+)

| Code | Language | Code | Language |
|------|---------|------|---------|
| `en` | English | `ja` | Japanese |
| `es` | Spanish | `zh-cn` | Chinese (Simplified) |
| `fr` | French | `zh-tw` | Chinese (Traditional) |
| `de` | German | `hi` | Hindi |
| `it` | Italian | `ar` | Arabic |
| `pt` | Portuguese | `ko` | Korean |
| `ru` | Russian | *…* | More via langdetect |

### Processing Pipeline

```
1. Upload documents
2. langdetect → identify language per document
3. If not English → Claude Opus 4.6 translates to English
   (preserving technical terms, names, company names)
4. Analysis runs entirely on English content
5. Results show original detected language + translation status
```

### UI Controls

- **"🌐 Show Language Detection" checkbox** — preview detected languages before submitting.
- **"🌐 Language Information" expander** in results — shows translation status per document.

### Language Handler API

```python
class LanguageHandler:
    def detect_language(text: str) -> Tuple[str, str]
        # Returns (language_code, language_name)

    def translate_to_english(text: str, source_language: str) -> Tuple[str, bool]
        # Returns (translated_text, was_translated)

    def process_content(content: str) -> Dict
        # Full single-document pipeline

    def process_batch(items: list) -> Dict
        # Batch pipeline for multiple documents
```

### Example: German Resume + English Job Description

```
Input:
  Job Description: English
  Resume 1: German (auto-detected)
  Resume 2: English

Steps:
  1. Detect: Resume 1 → German
  2. Translate: German → English (Claude Opus 4.6)
  3. Analyze: All content now in English
  4. Results: Resume 1 marked "Translated from German"
```

---

## 6. Authentication & Login

### How It Works

Access to MatchMuse is fully gated by a login page. No analysis functionality is accessible without a valid session.

- Credentials are read **only from environment variables** (`MATCHMUSE_USERNAME`, `MATCHMUSE_PASSWORD`).
- Credentials are **never stored** in source code or config files.
- Session state is managed by Streamlit — refreshing the page or closing the browser resets the session.
- A **Logout** button is available in the sidebar at all times during an active session.

### Environment Variables Required

```bash
MATCHMUSE_USERNAME=your_username
MATCHMUSE_PASSWORD=your_secure_password
```

### Login Flow

```
Browser opens MatchMuse URL
       │
       ▼
st.session_state.authenticated == False?
       │  YES
       ▼
Render login form (username + password)
       │
       ▼
_check_credentials() compares against env vars
       │  Match?
   YES │           NO
       ▼           ▼
Set authenticated=True   Show error "Invalid credentials"
st.rerun()
       │
       ▼
Main application (full functionality)
```

### Security Notes

- Passwords are entered via Streamlit's `type="password"` input — masked in the browser.
- The `_check_credentials()` function uses direct string comparison (suitable for single-user / small-team tools). For multi-user production systems, consider bcrypt hashing.
- Set a strong, random password when deploying on Render.

---

## 7. Deployment on Render

### One-Click Deploy with `render.yaml`

The repository includes a `render.yaml` Blueprint file. Render will automatically configure the web service when you connect the repository.

```yaml
# render.yaml (summary)
services:
  - type: web
    name: matchmuse
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run app_streamlit.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --server.enableCORS false
```

### Step-by-Step Deployment

1. **Push this repository** to GitHub (or GitLab).
2. Log in to [render.com](https://render.com) → **New → Blueprint**.
3. Connect your repository. Render detects `render.yaml` automatically.
4. Set the required **Secret Environment Variables** in the Render dashboard:

   | Variable | Value |
   |----------|-------|
   | `NEXUS_API_KEY` | Your GenAI-Nexus API key |
   | `MATCHMUSE_USERNAME` | Login username |
   | `MATCHMUSE_PASSWORD` | Login password |

5. Click **Apply** — Render builds and deploys the service.
6. Visit the generated `.onrender.com` URL and sign in.

### Render Environment Variables (auto-set)

| Variable | Value |
|----------|-------|
| `NEXUS_API_URL` | `https://genai-nexus.api.corpinter.net/` |
| `STREAMLIT_SERVER_HEADLESS` | `true` |
| `STREAMLIT_BROWSER_GATHER_USAGE_STATS` | `false` |
| `PORT` | Set by Render automatically |

### Important Notes

- **Free tier** on Render spins down after 15 minutes of inactivity; first request after spin-down may take 30–60 seconds.
- Uploaded files are stored in `/tmp` — they are ephemeral and cleaned up per request.
- The `.streamlit/config.toml` configures Streamlit to bind on `0.0.0.0` and disables usage stats for production.

### Redeployment

Any push to the connected branch triggers an automatic redeploy on Render.

---

## 8. Testing Guide

### Sample Files

| File | Description |
|------|------------|
| `samples/sample_job_description.txt` | Senior Software Engineer at TechCorp Solutions |
| `samples/resume_john_doe.txt` | 7 years exp, Java/Python/Node.js, AWS certified |
| `samples/resume_sarah_johnson.txt` | 5 years exp, Full Stack, React focus |
| `samples/resume_michael_chen.txt` | 8+ years exp, DevOps Lead |

### Test Scenario 1: Basic Ranking

1. Start the app: `streamlit run app_streamlit.py`
2. Sign in.
3. Paste content from `samples/sample_job_description.txt`.
4. Upload all three resume files.
5. Click "Analyze Resumes".

**Expected ranking order:**
1. **John Doe** — best keyword match, progressive career, AWS certified
2. **Michael Chen** — most experience but DevOps-focused (less full-stack)
3. **Sarah Johnson** — minimum experience, good React skills

### Test Scenario 2: API Connectivity

```bash
source .venv/bin/activate
python debug_api.py
```

Expected output:
```
✅ RANKINGS FOUND!
  Number of rankings: 2
  Ranking 1: John Doe - Score: 88%
```

### Test Scenario 3: Multilingual

```bash
bash test_multilingual.sh
```

or:

```bash
python test_multilingual.py
```

### Test Scenario 4: Environment Verification

```bash
bash verify.sh
```

---

## 9. Debug Strategies

### Problem: Empty Results ("No rankings available")

The API may be working correctly but the response is not parsed as expected.

**Step 1 — Check API directly:**
```bash
python debug_api.py
```

**Step 2 — Use plain TXT files first.** PDFs with scanned images yield no extractable text; switch to text-based PDFs or TXT files.

**Step 3 — Check job description length.** Minimum 50 characters; longer descriptions produce better Claude responses.

**Step 4 — Look at the debug expander** in the Streamlit results panel:
- "🔍 API Response (Debug)" — shows the raw API response if the format was unexpected.
- "⚠️ API returned empty response" — network or credential issue.

### Problem: Translation Fails

- Verify `NEXUS_API_KEY` is set correctly.
- Translation uses the same Claude Opus 4.6 endpoint; if ranking works, translation should too.
- Short texts (< 10 chars) skip translation automatically.

### Problem: PDF Text Extraction Empty

- PDFs must be **text-based** (not scanned images).
- Use `pdftotext yourfile.pdf -` to verify extractable text before uploading.
- Fallback: convert to `.txt` and upload that instead.

### Problem: `NEXUS_API_KEY` Not Set

```
⚠️ Configuration Error: NEXUS_API_KEY environment variable not set
```

- Local: ensure `.env` exists and `NEXUS_API_KEY` is populated.
- Render: add the variable in the Render dashboard under Environment.

### Problem: Login Credentials Not Working

```
⚠️ Server misconfiguration: MATCHMUSE_USERNAME / MATCHMUSE_PASSWORD not set
```

- Both `MATCHMUSE_USERNAME` and `MATCHMUSE_PASSWORD` must be set in the environment.
- Local: check `.env`.
- Render: check the Environment tab in the service dashboard.

### Problem: `ModuleNotFoundError`

```bash
pip install -r requirements.txt
```

Ensure the virtual environment is activated before running.

---

## 10. Migration Notes (Flask → Streamlit)

The original codebase used a **Flask REST API + HTML/CSS/JS frontend**. It was migrated to **Streamlit** to simplify deployment and use the correct boto3 API integration.

### What Changed

| Aspect | Before (Flask) | After (Streamlit) |
|--------|---------------|------------------|
| Frontend | HTML5 + CSS3 + Vanilla JS | Streamlit Python widgets |
| Backend | Flask REST API (`/api/analyze`) | Streamlit session state |
| API client | `requests` (HTTP REST) | `boto3` (AWS Bedrock) |
| Auth | None | Session-state login (env-var credentials) |
| Deployment | 2 separate codebases | Single `app_streamlit.py` |
| PDF export | Not available | fpdf2 inline generation |

### Kept Unchanged

- `resume_processor.py` — file parsing logic unchanged.
- `ranking_engine.py` — keyword extraction unchanged.
- `language_handler.py` — language detection unchanged.
- `nexus_client.py` — updated from REST to boto3 in an earlier migration; unchanged since.
- Sample files in `samples/`.

### Legacy Files (kept for reference)

- `app.py` — Flask application (not used in production).
- `templates/index.html`, `static/styles.css`, `static/script.js` — Flask frontend assets.

---

## 11. Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `NEXUS_API_KEY` | **Yes** | GenAI-Nexus / AWS Bedrock API key | `abc123...` |
| `NEXUS_API_URL` | No | Nexus API endpoint (has default) | `https://genai-nexus.api.corpinter.net/` |
| `MATCHMUSE_USERNAME` | **Yes** | Login username for the tool | `admin` |
| `MATCHMUSE_PASSWORD` | **Yes** | Login password for the tool | `s3cur3P@ss!` |
| `STREAMLIT_SERVER_PORT` | No | Port (auto-set by Render) | `8501` |
| `STREAMLIT_SERVER_HEADLESS` | No | Must be `true` in production | `true` |
| `STREAMLIT_BROWSER_GATHER_USAGE_STATS` | No | Set `false` to disable telemetry | `false` |

### `.env` Template

```bash
# Copy .env.example to .env and fill in values
NEXUS_API_KEY=your_nexus_api_key_here
NEXUS_API_URL=https://genai-nexus.api.corpinter.net/
MATCHMUSE_USERNAME=your_username_here
MATCHMUSE_PASSWORD=your_secure_password_here
```

---

*MatchMuse is an internal recruitment tool. Treat API keys and login credentials as secrets — never commit `.env` to source control.*
