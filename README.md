# LearnLab — AI-Powered Learning & Certification Platform

A complete 4-step learning journey: **sign up/sign in with email OTP → describe
any topic and get an AI-generated lesson → take a 20-question test → earn a
downloadable certificate.** Every user, OTP, session, test attempt, and
certificate issued is logged to an Excel workbook (`data/learnlab.xlsx`).

## The 4 pages

1. **Sign in / Sign up** — create an account or log in, then verify a 6-digit
   one-time code sent to your email (real SMTP email if configured; otherwise
   shown on-screen in a clearly labelled "dev mode" banner so you can test
   without any setup).
2. **Learn** — type or describe any topic. You get back a structured lesson
   (summary, sections, key concepts), a YouTube search link for a tutorial on
   that exact topic, 3 worked example cases, and 5 quick mock-check questions.
3. **Test** — a 20-question multiple-choice test generated specifically for
   the topic you described, with a progress bar and instant scoring.
4. **Certificate** — score 60% or higher and claim a downloadable PDF
   certificate of completion with your name, topic, score, and a unique
   certificate ID.

## What's real vs. what needs a key

- **Always works, no setup required:** accounts, OTP flow (dev-mode banner),
  the full 4-screen journey, test grading, PDF certificate generation, and
  Excel logging of everything.
- **Needs `ANTHROPIC_API_KEY`:** AI-generated lessons and test questions that
  are actually tailored to the topic typed in. Without a key, the app still
  runs completely — it shows clearly-labelled placeholder content instead of
  failing, so you can see the full flow immediately.
- **Needs SMTP credentials:** real OTP delivery to an inbox. Without them, the
  OTP is shown directly on the verification screen in a "dev mode" banner.

## Project structure

```
learnlab/
├── backend/
│   ├── app.py                 # Flask app: all routes
│   ├── datastore.py            # Excel-backed data layer (openpyxl)
│   ├── mailer.py                # SMTP email OTP sender (+ dev fallback)
│   ├── content_generator.py     # Claude-powered lesson + test generator (+ fallback)
│   ├── certificate.py           # PDF certificate generator (reportlab)
│   └── requirements.txt
├── frontend/
│   ├── index.html               # all 4 screens (single-page app)
│   ├── style.css                # "learning journey" visual design
│   └── script.js                 # screen navigation + all API calls
└── data/                        # created automatically on first run
    ├── learnlab.xlsx            # Users / OTPs / Sessions / TestAttempts / Certificates
    └── certificates/*.pdf       # every issued certificate
```

## Setup

```bash
cd learnlab/backend
python3 -m venv venv && source venv/bin/activate      # optional but recommended
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000** — Flask serves both the frontend and the API.

### Enable real AI-generated lessons & questions (recommended)

1. In `backend/`, copy `.env.example` to a new file named `.env`.
2. Open `.env` and paste your key after `ANTHROPIC_API_KEY=` (get one at
   https://console.anthropic.com/settings/keys).
3. Restart `python app.py`.

That's it — the app reads `.env` automatically on startup (via
`python-dotenv`). You never need to type your key into a terminal command or
share it anywhere. **Never commit `.env` or paste your real key into chat,
docs, or version control** — `.gitignore` is already set up to exclude it.

You can confirm it picked up the key by visiting `http://localhost:5000/api/health`
— it should show `"ai_configured": true`. If your key is invalid or missing,
the app doesn't break; it automatically falls back to clearly-labelled
placeholder content instead.

### Enable real email OTP delivery (optional)

Add these to the same `.env` file:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your-gmail-app-password     # Gmail: create an "App Password", not your normal password
SMTP_FROM=you@gmail.com
```

Without these, the app still runs completely — you'll just see the OTP shown
directly on-screen in a "dev mode" banner instead of it being emailed.

## Viewing the logged data

Every account, OTP, learning session, test attempt, and certificate is
written to `data/learnlab.xlsx` as it happens — open it directly in Excel, or
click **"Export full data (Excel)"** at the bottom of the certificate page to
download it from the running app at any time (also available directly at
`/api/data/export`).

## Notes on the design

The visual identity is a warm, academic "learning journey" — a serif display
font for headings, a warm paper background, indigo as the primary action
color, amber/gold for certificate and highlight moments — with a 4-stage
progress stepper always visible at the top so the student always knows where
they are in the journey.

## Extending this further

- Swap the in-memory session tokens for a proper session store (Redis) if
  deploying beyond a single process.
- Add password reset (same OTP mechanism, a new `purpose`).
- Persist `TEST_CACHE` (currently in-memory) to disk/Redis so test sessions
  survive a server restart.
- Add a teacher/admin view that reads `learnlab.xlsx` directly to see
  aggregate performance across all students and topics.
