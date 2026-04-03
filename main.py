"""
main.py
Entry point for the GI Research Digest pipeline.
Run manually: python main.py
Or scheduled via GitHub Actions (see .github/workflows/weekly_digest.yml)

Required environment variables:
  GEMINI_API_KEY      – your free Google Gemini API key (aistudio.google.com)
  SENDER_EMAIL        – email address to send from
  SMTP_PASSWORD       – app password for SMTP sender
  RECIPIENT_EMAIL     – your email address (can be same as sender)

Optional:
  SMTP_HOST           – default: smtp.gmail.com
  SMTP_PORT           – default: 587
  DAYS_BACK           – days of literature to cover (default: 7)
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from fetch_and_summarise import run_digest
from generate_pdf import generate_pdf
from send_email import send_digest_smtp


def main():
    # ── Config from environment ────────────────────────────────────────────────
    api_key = os.environ.get("GEMINI_API_KEY")
    sender_email = os.environ.get("SENDER_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    recipient_email = os.environ.get("RECIPIENT_EMAIL", sender_email)
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    days_back = int(os.environ.get("DAYS_BACK", "7"))

    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        sys.exit(1)
    if not sender_email or not smtp_password:
        print("❌ SENDER_EMAIL and SMTP_PASSWORD must be set")
        sys.exit(1)

    # ── Run pipeline ───────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  GI RESEARCH DIGEST  |  " + datetime.now().strftime("%d %B %Y"))
    print("═" * 60 + "\n")

    # 1. Fetch and summarise
    digest_data = run_digest(api_key=api_key, days_back=days_back)

    if not digest_data["hepatology"] and not digest_data["luminal_gi"]:
        print("⚠️  No papers found for this period. Email not sent.")
        sys.exit(0)

    # 2. Generate PDF
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    pdf_path = output_dir / f"GI_Digest_{date_str}.pdf"
    generate_pdf(digest_data, str(pdf_path))

    # 3. Send email
    print(f"\n📧 Sending email to {recipient_email}...")
    send_digest_smtp(
        digest_data=digest_data,
        pdf_path=str(pdf_path),
        recipient_email=recipient_email,
        sender_email=sender_email,
        smtp_password=smtp_password,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
    )

    print("\n🎉 Digest complete!\n")


if __name__ == "__main__":
    main()
