"""
send_email.py
Sends the weekly digest PDF via SMTP.
Supports a mailing list — set RECIPIENT_EMAILS as a comma-separated list of addresses.
e.g. RECIPIENT_EMAILS=you@nhs.net,colleague@nhs.net,another@gmail.com
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from pathlib import Path


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
           background: #f3f4f6; margin: 0; padding: 20px; color: #374151; }}
    .container {{ max-width: 600px; margin: 0 auto; background: white;
                  border-radius: 12px; overflow: hidden;
                  box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    .header {{ background: #1B3A5C; padding: 28px 32px; }}
    .header h1 {{ color: white; margin: 0; font-size: 22px; font-weight: 700; }}
    .header p {{ color: #BDD6E6; margin: 4px 0 0; font-size: 13px; }}
    .stats {{ display: flex; background: #0B7285; }}
    .stat {{ flex: 1; padding: 14px; text-align: center; }}
    .stat .num {{ font-size: 24px; font-weight: 700; color: white; }}
    .stat .lbl {{ font-size: 11px; color: #93C5D8; margin-top: 2px; }}
    .body {{ padding: 28px 32px; }}
    .section {{ margin-bottom: 24px; }}
    .section-title {{ font-size: 15px; font-weight: 700; color: #1B3A5C;
                      border-left: 4px solid #0B7285; padding-left: 10px;
                      margin-bottom: 12px; }}
    .paper {{ background: #f8fafc; border-radius: 8px; padding: 12px 14px;
              margin-bottom: 8px; border-left: 3px solid #0B7285; }}
    .paper-title {{ font-weight: 600; font-size: 13px; color: #1B3A5C; margin-bottom: 4px; }}
    .paper-meta {{ font-size: 11px; color: #6B7280; margin-bottom: 6px; }}
    .paper-finding {{ font-size: 12px; color: #374151; }}
    .badge {{ display: inline-block; font-size: 10px; padding: 2px 7px;
              border-radius: 10px; font-weight: 600; margin-right: 6px; }}
    .high {{ background: #dcfce7; color: #16A34A; }}
    .moderate {{ background: #fef3c7; color: #D97706; }}
    .preliminary {{ background: #fee2e2; color: #DC2626; }}
    .footer {{ background: #f3f4f6; padding: 16px 32px; font-size: 11px;
               color: #9CA3AF; text-align: center; line-height: 1.6; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>GI Research Digest</h1>
      <p>Week ending {date}  ·  {total} papers reviewed</p>
    </div>
    <div class="stats">
      <div class="stat"><div class="num">{hep_count}</div><div class="lbl">Hepatology</div></div>
      <div class="stat"><div class="num">{hpb_count}</div><div class="lbl">HPB</div></div>
      <div class="stat"><div class="num">{gi_count}</div><div class="lbl">Luminal GI</div></div>
      <div class="stat"><div class="num">{endo_count}</div><div class="lbl">Endoscopy</div></div>
    </div>
    <div class="body">
      <p style="font-size:13px; margin-top:0;">Your weekly digest is attached as a PDF.
      Below is a quick summary of the top highlights from each section.</p>
      {hep_section}
      {hpb_section}
      {gi_section}
      {endo_section}
    </div>
    <div class="footer">
      AI-generated from PubMed abstracts for educational purposes only.<br>
      Not clinical advice. Always consult full-text articles before applying findings to patient care.<br>
      To unsubscribe from this digest, contact the sender.
    </div>
  </div>
</body>
</html>
"""

PAPER_ROW = """
<div class="paper">
  <div class="paper-title">
    <span class="badge {quality_class}">{quality_label}</span>
    [{subcategory}] {title}
  </div>
  <div class="paper-meta">{journal} · {study_type}</div>
  <div class="paper-finding">{headline}</div>
</div>
"""

SECTION_BLOCK = """
<div class="section">
  <div class="section-title">{title}</div>
  {papers}
</div>
"""


def _build_section_html(title, papers, max_papers=3):
    if not papers:
        return ""
    paper_html = ""
    for p in papers[:max_papers]:
        qf = p.get("quality_flag", "moderate")
        q_label = {"high": "High Quality", "moderate": "Moderate",
                   "preliminary": "Preliminary"}.get(qf, qf)
        paper_html += PAPER_ROW.format(
            quality_class=qf,
            quality_label=q_label,
            subcategory=p.get("subcategory", ""),
            title=p.get("title", "")[:100] + ("..." if len(p.get("title", "")) > 100 else ""),
            journal=p.get("journal", ""),
            study_type=p.get("study_type", ""),
            headline=p.get("headline", ""),
        )
    if len(papers) > max_papers:
        paper_html += (f'<p style="font-size:11px;color:#6B7280;margin:6px 0 0 4px;">'
                       f'+ {len(papers)-max_papers} more in the full PDF</p>')
    return SECTION_BLOCK.format(title=title, papers=paper_html)


def build_html_body(digest_data):
    hepatology = digest_data.get("hepatology", [])
    hpb        = digest_data.get("hpb", [])
    luminal    = digest_data.get("luminal", [])
    endoscopy  = digest_data.get("endoscopy", [])
    total      = len(hepatology) + len(hpb) + len(luminal) + len(endoscopy)

    return HTML_TEMPLATE.format(
        date=datetime.now().strftime("%d %B %Y"),
        total=total,
        hep_count=len(hepatology),
        hpb_count=len(hpb),
        gi_count=len(luminal),
        endo_count=len(endoscopy),
        hep_section=_build_section_html("🫀 Hepatology", hepatology),
        hpb_section=_build_section_html("🔬 HPB", hpb),
        gi_section=_build_section_html("🔭 Luminal GI", luminal),
        endo_section=_build_section_html("🩺 Endoscopy", endoscopy),
    )


def send_digest_smtp(
    digest_data: dict,
    pdf_path: str,
    recipient_emails: list[str],
    sender_email: str,
    smtp_password: str,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
):
    """
    Send the digest to a list of recipients via SMTP.
    Each recipient gets their own individual email (BCC-style privacy).
    """
    end_date   = datetime.now()
    start_date = end_date - timedelta(days=7)
    subject    = (f"GI Research Digest | "
                  f"{start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')}")

    html_body = build_html_body(digest_data)
    pdf_bytes = open(pdf_path, "rb").read()
    pdf_filename = Path(pdf_path).name

    total     = len(recipient_emails)
    successes = 0
    failures  = []

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(sender_email, smtp_password)

        for recipient in recipient_emails:
            recipient = recipient.strip()
            if not recipient:
                continue
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"]    = sender_email
                msg["To"]      = recipient

                plain = (
                    f"Your weekly GI Research Digest is attached.\n\n"
                    f"Hepatology: {len(digest_data.get('hepatology', []))} papers\n"
                    f"HPB: {len(digest_data.get('hpb', []))} papers\n"
                    f"Luminal GI: {len(digest_data.get('luminal', []))} papers\n"
                    f"Endoscopy: {len(digest_data.get('endoscopy', []))} papers\n\n"
                    f"Please open the attached PDF for full summaries."
                )
                msg.attach(MIMEText(plain, "plain"))
                msg.attach(MIMEText(html_body, "html"))

                # Attach PDF
                part = MIMEBase("application", "octet-stream")
                part.set_payload(pdf_bytes)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
                msg.attach(part)

                server.sendmail(sender_email, recipient, msg.as_string())
                print(f"   ✅ Sent to {recipient}")
                successes += 1

            except Exception as e:
                print(f"   ✗ Failed to send to {recipient}: {e}")
                failures.append(recipient)

    print(f"\n📧 Email summary: {successes}/{total} sent successfully")
    if failures:
        print(f"   Failed recipients: {', '.join(failures)}")
