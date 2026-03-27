# SmartMail AI: Intelligent Email Assistant

SmartMail AI is a full-stack AI-powered email assistant. It supports Gmail inbox sync plus AI-powered email classification, priority ranking, explainability, summarization, and multilingual email understanding for English, Hindi, and Marathi.

## Stack

- Frontend: React + Vite
- Backend: FastAPI + Transformers + Gmail API
- NLP approach: Zero-shot transformer classification with DistilBERT MNLI for English, multilingual keyword-based fallback for Hindi and Marathi, AI-style priority ranking, explainability, and email summarization with a local fallback mode when model weights are not available yet

## Features

- Manual single-email classification
- Multi-language support for English, Hindi, and Marathi
- AI email summarization for long emails
- Explainable AI with keyword-based reasons
- Priority inbox ranking with `Urgent`, `Medium`, and `Low`
- Gmail inbox connection with local OAuth
- Inbox sync to load recent Gmail messages
- Select one Gmail message and inspect its full analysis
- Confidence scores for every supported label
- Language detection shown in both manual analysis and Gmail inbox cards

Supported labels:

- Work
- Personal
- Promotions
- Finance
- Urgent
- Job
- Events
- Social
- Spam
- Phishing

## Run the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API starts at `http://127.0.0.1:8000`.

If you also want transformer inference instead of fallback mode, install the optional ML stack after the base install:

```bash
pip install -r requirements-ml.txt
```

Useful endpoints:

- `GET /health`
- `POST /api/classify`
- `GET /api/gmail/status`
- `GET /api/gmail/classify?max_results=15&query=category:primary`

Example manual request body:

```json
{
  "sender": "alerts@secure-payments.com",
  "subject": "Urgent: verify your account",
  "body": "Click the link below immediately to confirm your login details."
}
```

## Gmail setup

1. Open Google Cloud Console and create or select a project.
2. Enable the Gmail API for that project.
3. Create OAuth client credentials of type `Desktop app`.
4. Download the client secret JSON file.
5. Save that file as `backend/credentials.json`.
6. If Google blocks sign-in with `Error 403: access_denied`, open `Google Auth Platform` -> `Audience` and add your Gmail address under `Test users`.

Optional environment variables:

```bash
GMAIL_OAUTH_CREDENTIALS_FILE=C:\path\to\credentials.json
GMAIL_OAUTH_TOKEN_FILE=C:\path\to\.gmail-token.json
```

How the local Gmail flow works:

- Open the frontend and click `Connect Gmail and Rank Inbox`
- On the first sync, the backend opens a Google sign-in window in your browser
- After consent, a local token file is stored in `backend/.gmail-token.json`
- Messages are ranked by AI priority and each one gets a short summary
- Each email also shows its detected language
- Select one inbox email to inspect its summary, priority, category, explanation, and language in detail

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

The app starts at `http://127.0.0.1:5173`.

If you need a different backend URL, create a `.env` file in `frontend`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Notes

- The base backend install is intentionally lightweight except for the Gmail client libraries.
- If the ML dependencies are missing or the model cannot be loaded, the backend automatically falls back to deterministic keyword scoring and extractive summarization so the demo remains usable during setup.
- English emails can use transformer inference when the optional ML stack is available. Hindi and Marathi currently use a deterministic multilingual keyword fallback so the project remains lightweight and reliable during demos.
- Gmail sync currently uses read-only access and classifies recent messages; it does not move, label, or delete emails.
- Do not commit `backend/credentials.json`, `backend/.gmail-token.json`, or local `.env` files to Git.
- In WSL, large package downloads can fail with `/tmp` I/O errors. If optional ML installation fails, retry with a writable temp directory:

```bash
mkdir -p ~/pip-tmp
TMPDIR=~/pip-tmp pip install --no-cache-dir -r requirements-ml.txt
```
