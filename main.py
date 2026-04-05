"""
main.py
Entry point for the GI Research Digest pipeline.

Required environment variables:
  ANTHROPIC_API_KEY   – your Anthropic API key (console.anthropic.com)
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
    api_key        = os.environ.get("ANTHROPIC_API_KEY")
    sender_email   = os.environ.get("SENDER_EMAIL")
    smtp_password  = os.environ.get("SMTP_PASSWORD")
    recipient_email = os.environ.get("RECIPIENT_EMAIL", sender_email)
    smtp_host      = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port      = int(os.environ.get("SMTP_PORT", "587"))
    days_back      = int(os.environ.get("DAYS_BACK", "7"))

    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        sys.exit(1)
    if not sender_email or not smtp_password:
        print("❌ SENDER_EMAIL and SMTP_PASSWORD must be set")
        sys.exit(1)

    print("\n" + "═" * 60)
    print("  GI RESEARCH DIGEST  |  " + datetime.now().strftime("%d %B %Y"))
    print("═" * 60 + "\n")

    digest_data = run_digest(api_key=api_key, days_back=days_back)

    if not digest_data["hepatology"] and not digest_data["luminal"] and not digest_data["hpb"] and not digest_data["endoscopy"]:
        print("⚠️  No papers found for this period. Email not sent.")
        sys.exit(0)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    pdf_path = output_dir / f"GI_Digest_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    generate_pdf(digest_data, str(pdf_path))

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
