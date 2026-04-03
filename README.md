# GI Research Digest

Automated weekly literature review for gastroenterology and hepatology.
Fetches new papers from 20 high-impact journals, summarises each with Claude AI,
and emails a formatted PDF every Friday afternoon.

---

## How it works

```
PubMed API          Claude API           ReportLab           SMTP
(free, no key) ──►  (summarise &    ──►  (generate      ──►  (email PDF
                     categorise)          PDF)                 to you)
```

1. **Fetch** – Queries PubMed for papers published in the past 7 days across 20 journals
2. **Filter** – Removes letters, editorials, errata, and papers with no abstract
3. **Summarise** – Claude categorises each paper (hepatology / luminal GI) and generates: headline finding, key findings, clinical relevance, study type, quality rating
4. **PDF** – ReportLab builds a clean A4 digest with two sections, highlights boxes, and quality badges
5. **Email** – Sent via SMTP with HTML preview in email body and PDF attached

---

## Journals covered

| Journal | Region |
|---|---|
| Gut | UK (BSG) |
| Frontline Gastroenterology | UK (BSG) |
| BMJ Open Gastroenterology | UK |
| Gastroenterology | USA (AGA) |
| American Journal of Gastroenterology | USA (ACG) |
| Clinical Gastroenterology & Hepatology | USA (AGA) |
| NEJM | USA |
| The Lancet | UK |
| Lancet Gastroenterology & Hepatology | UK |
| BMJ | UK |
| Nature Medicine | International |
| Journal of Hepatology | Europe (EASL) |
| JHEP Reports | Europe (EASL) |
| Hepatology | USA (AASLD) |
| Liver International | International |
| Alimentary Pharmacology & Therapeutics | UK |
| UEG Journal | Europe (UEG) |
| Colorectal Disease | UK (ACPGBI) |
| Endoscopy | Europe (ESGE) |
| Endoscopy International Open | Europe (ESGE) |

---

## Setup (one time, ~15 minutes)

### 1. Fork / clone this repository

```bash
git clone https://github.com/YOUR_USERNAME/gi-digest.git
cd gi-digest
```

### 2. Get your API keys

**Google Gemini API key (free — no credit card needed)**
- Go to **aistudio.google.com**
- Sign in with a Google account
- Click **Get API Key** → **Create API key**
- Copy the key — it looks like `AIzaSy...`
- The free tier allows 1,500 requests/day — far more than needed for this digest

**Gmail App Password** (recommended — works reliably, free)
- Go to your Google Account → Security → 2-Step Verification → App passwords
- Create an app password for "Mail"
- Copy the 16-character password

**NHS mail / Outlook alternative**
- Use `SMTP_HOST=smtp.office365.com` and `SMTP_PORT=587`
- Use your full NHS email and password (or app password if MFA enabled)

### 3. Add GitHub Secrets

In your GitHub repository: Settings → Secrets and variables → Actions → New repository secret

| Secret name | Value |
|---|---|
| `GEMINI_API_KEY` | Your free Gemini API key from aistudio.google.com |
| `SENDER_EMAIL` | Email to send from (e.g. yourname@gmail.com) |
| `SMTP_PASSWORD` | App password from step 2 |
| `RECIPIENT_EMAIL` | Email to receive digest (can be same or different) |
| `SMTP_HOST` | `smtp.gmail.com` (or `smtp.office365.com` for NHS mail) |
| `SMTP_PORT` | `587` |

### 4. Enable GitHub Actions

- Go to your repo → Actions tab → Enable workflows
- The digest will run automatically every Friday at 17:00 UTC

### 5. Test it manually

In the Actions tab → "Weekly GI Research Digest" → "Run workflow" → Run

---

## Running locally

```bash
pip install -r requirements.txt

export GEMINI_API_KEY="AIzaSy..."
export SENDER_EMAIL="you@gmail.com"
export SMTP_PASSWORD="your-app-password"
export RECIPIENT_EMAIL="you@nhs.net"

python main.py
```

The PDF will also be saved to `output/GI_Digest_YYYY-MM-DD.pdf`.

---

## Customisation

### Change delivery schedule
Edit `.github/workflows/weekly_digest.yml`:
```yaml
- cron: "0 17 * * 5"   # Friday 17:00 UTC
- cron: "0 8 * * 1"    # Monday 08:00 UTC
- cron: "0 18 * * 0"   # Sunday 18:00 UTC
```

### Add or remove journals
Edit the `JOURNALS` list in `fetch_and_summarise.py`.
Use PubMed journal title abbreviations (search at https://www.ncbi.nlm.nih.gov/nlmcatalog).

### Change summary depth
Edit `SYSTEM_PROMPT` in `fetch_and_summarise.py` to request more or less detail.

### Cover more than 7 days
Set `DAYS_BACK=14` in your environment or GitHub secrets to catch up after holidays.

---

## File structure

```
gi-digest/
├── main.py                  # Entry point — orchestrates the pipeline
├── fetch_and_summarise.py   # PubMed fetch + Claude summarisation
├── generate_pdf.py          # ReportLab PDF builder
├── send_email.py            # SMTP email sender
├── requirements.txt
├── .github/
│   └── workflows/
│       └── weekly_digest.yml   # GitHub Actions scheduler
└── output/                  # PDFs saved here (gitignored)
```

---

## Disclaimer

This tool is for **educational purposes only**. AI-generated summaries are derived from
abstracts and may not fully represent the original paper. Always read the full text before
applying any findings to clinical practice. Not a substitute for clinical judgement.
