"""
send_email.py
Sends the weekly digest PDF via SMTP.
Supports a mailing list — set RECIPIENT_EMAILS as a comma-separated list of addresses.
e.g. RECIPIENT_EMAILS=you@nhs.net,colleague@nhs.net,another@gmail.com
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.utils import formataddr
from datetime import datetime, timedelta
from html import escape
from pathlib import Path


SITE_URL   = "https://rexhepatis.org"
CROWN_PATH = Path(__file__).resolve().parent / "assets" / "brand" / "crown-email.png"
CROWN_CID  = "rexhepatis-crown"

# Rex Hepatis branding (rexhepatis.org): navy #0E1A2E, blue #2C6DBA, gold #C99A2E,
# Newsreader headings and IBM Plex Sans text, with Georgia / system fallbacks for
# mail apps that don't load web fonts.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=Newsreader:opsz,wght@6..72,600&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'IBM Plex Sans', -apple-system, 'Segoe UI', Arial, sans-serif;
           background: #F3F5F9; margin: 0; padding: 20px; color: #33415C; }}
    .container {{ max-width: 600px; margin: 0 auto; background: white;
                  border-radius: 10px; overflow: hidden;
                  box-shadow: 0 2px 8px rgba(14,26,46,0.08); }}
    .header {{ background: #0E1A2E; padding: 24px 32px 26px;
               border-left: 4px solid #2C6DBA; }}
    .brand {{ font-family: 'Newsreader', Georgia, serif; font-size: 15px; font-weight: 600;
              color: #C99A2E; margin: 0 0 10px; }}
    .brand img {{ height: 18px; width: auto; vertical-align: -3px; margin-right: 6px; border: 0; }}
    .header h1 {{ font-family: 'Newsreader', Georgia, serif; color: white; margin: 0;
                  font-size: 28px; font-weight: 600; line-height: 1.15; }}
    .header p {{ color: #C9D4E5; margin: 6px 0 0; font-size: 13px; }}
    .stats {{ display: flex; background: #13223A; border-bottom: 3px solid #2C6DBA; }}
    .stat {{ flex: 1; padding: 14px; text-align: center; }}
    .stat .num {{ font-family: 'Newsreader', Georgia, serif; font-size: 26px;
                  font-weight: 600; color: white; }}
    .stat .lbl {{ font-size: 11px; color: #6FA8EC; margin-top: 2px; }}
    .body {{ padding: 28px 32px; }}
    .section {{ margin-bottom: 24px; }}
    .section-title {{ font-family: 'Newsreader', Georgia, serif; font-size: 17px;
                      font-weight: 600; color: #0E1A2E;
                      border-left: 4px solid #2C6DBA; padding-left: 10px;
                      margin-bottom: 12px; }}
    .paper {{ background: #F5F8FC; border-radius: 6px; padding: 12px 14px;
              margin-bottom: 8px; border-left: 3px solid #2C6DBA; }}
    .paper-title {{ font-weight: 600; font-size: 13px; color: #0E1A2E; margin-bottom: 4px; }}
    .paper-meta {{ font-size: 11px; color: #4A5872; margin-bottom: 6px; }}
    .paper-finding {{ font-size: 12px; color: #33415C; }}
    .badge {{ display: inline-block; font-size: 10px; padding: 2px 7px;
              border-radius: 10px; font-weight: 600; margin-right: 6px; }}
    .high {{ background: #E3F3EA; color: #1E8A4C; }}
    .moderate {{ background: #FBF5E6; color: #7C560E; }}
    .preliminary {{ background: #FBE9EA; color: #C0262D; }}
    .footer {{ background: #F3F5F9; padding: 16px 32px; font-size: 11px;
               color: #4A5872; text-align: center; line-height: 1.6;
               border-top: 1px solid #D5DCE8; }}
    .footer a {{ color: #2C6DBA; font-weight: 600; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <p class="brand">{crown_img}Rex Hepatis</p>
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
      From <a href="{site_url}">Rex Hepatis</a> &middot; hepatobiliary learning, made accessible<br>
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
            subcategory=escape(p.get("subcategory", "")),
            title=escape(p.get("title", "")[:100] + ("..." if len(p.get("title", "")) > 100 else "")),
            journal=escape(p.get("journal", "")),
            study_type=escape(p.get("study_type", "")),
            headline=escape(p.get("headline", "")),
        )
    if len(papers) > max_papers:
        paper_html += (f'<p style="font-size:11px;color:#6B7280;margin:6px 0 0 4px;">'
                       f'+ {len(papers)-max_papers} more in the full PDF</p>')
    return SECTION_BLOCK.format(title=title, papers=paper_html)


def build_html_body(digest_data, include_crown=True):
    hepatology = digest_data.get("hepatology", [])
    hpb        = digest_data.get("hpb", [])
    luminal    = digest_data.get("luminal", [])
    endoscopy  = digest_data.get("endoscopy", [])
    total      = len(hepatology) + len(hpb) + len(luminal) + len(endoscopy)

    crown_img = (f'<img src="cid:{CROWN_CID}" alt="" width="27" height="18">'
                 if include_crown else "")
    return HTML_TEMPLATE.format(
        crown_img=crown_img,
        site_url=SITE_URL,
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
    days_back: int = 7,
) -> list[str]:
    """
    Send the digest to a list of recipients via SMTP.
    Each recipient gets their own individual email (BCC-style privacy).
    Returns the recipients the email could not be sent to.
    """
    end_date   = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    subject    = (f"GI Research Digest | "
                  f"{start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')}")

    crown_bytes = CROWN_PATH.read_bytes() if CROWN_PATH.exists() else None
    html_body = build_html_body(digest_data, include_crown=crown_bytes is not None)
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
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
                # multipart/mixed holding (text + HTML alternatives) + the PDF.
                # Putting the PDF inside "alternative" (as before) tells mail
                # clients it is a third version of the body, so some show the
                # PDF instead of the HTML or hide the attachment.
                msg = MIMEMultipart("mixed")
                msg["Subject"] = subject
                msg["From"]    = formataddr(("Rex Hepatis GI Digest", sender_email))
                msg["To"]      = recipient
                body = MIMEMultipart("alternative")

                plain = (
                    f"Your weekly GI Research Digest is attached.\n\n"
                    f"Hepatology: {len(digest_data.get('hepatology', []))} papers\n"
                    f"HPB: {len(digest_data.get('hpb', []))} papers\n"
                    f"Luminal GI: {len(digest_data.get('luminal', []))} papers\n"
                    f"Endoscopy: {len(digest_data.get('endoscopy', []))} papers\n\n"
                    f"Please open the attached PDF for full summaries.\n\n"
                    f"Rex Hepatis - {SITE_URL}"
                )
                body.attach(MIMEText(plain, "plain", "utf-8"))
                # HTML + the crown logo it shows inline (multipart/related)
                html_part = MIMEMultipart("related")
                html_part.attach(MIMEText(html_body, "html", "utf-8"))
                if crown_bytes:
                    logo = MIMEImage(crown_bytes, _subtype="png")
                    logo.add_header("Content-ID", f"<{CROWN_CID}>")
                    logo.add_header("Content-Disposition", "inline", filename="rex-hepatis.png")
                    html_part.attach(logo)
                body.attach(html_part)
                msg.attach(body)

                # Attach PDF
                part = MIMEApplication(pdf_bytes, _subtype="pdf")
                part.add_header("Content-Disposition", "attachment", filename=pdf_filename)
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
    return failures
