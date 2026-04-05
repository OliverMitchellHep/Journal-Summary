"""
generate_pdf.py
Generates a clean, professional PDF digest from the summarised paper data.
Uses ReportLab Platypus for flowing multi-page layout.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import BalancedColumns
from reportlab.lib.colors import HexColor
from datetime import datetime, timedelta
import os

# ── Colour palette ─────────────────────────────────────────────────────────────
NAVY       = HexColor("#1B3A5C")
TEAL       = HexColor("#0B7285")
LIGHT_TEAL = HexColor("#E8F4F7")
GOLD       = HexColor("#C8860A")
DARK_GOLD  = HexColor("#92610A")
LIGHT_GOLD = HexColor("#FDF6E3")
DEEP_GOLD  = HexColor("#78450A")
MID_GREY   = HexColor("#6B7280")
LIGHT_GREY = HexColor("#F3F4F6")
RED_FLAG   = HexColor("#DC2626")
GREEN_FLAG = HexColor("#16A34A")
AMBER_FLAG = HexColor("#D97706")
WHITE      = colors.white
BLACK      = colors.black

W, H = A4
MARGIN = 18 * mm

QUALITY_COLOURS = {
    "high":        (GREEN_FLAG, "● High Quality"),
    "moderate":    (AMBER_FLAG, "● Moderate"),
    "preliminary": (RED_FLAG,   "● Preliminary"),
}


# ── Style sheet ────────────────────────────────────────────────────────────────

def build_styles():
    base = getSampleStyleSheet()

    styles = {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"],
            fontSize=28, textColor=WHITE, alignment=TA_CENTER,
            spaceAfter=6, leading=34,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"],
            fontSize=13, textColor=HexColor("#BDD6E6"), alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "cover_date": ParagraphStyle(
            "cover_date", parent=base["Normal"],
            fontSize=11, textColor=HexColor("#93C5D8"), alignment=TA_CENTER,
        ),
        "section_header": ParagraphStyle(
            "section_header", parent=base["Heading1"],
            fontSize=18, textColor=WHITE, alignment=TA_LEFT,
            spaceAfter=0, spaceBefore=0, leading=22,
        ),
        "subsection": ParagraphStyle(
            "subsection", parent=base["Heading2"],
            fontSize=12, textColor=TEAL, spaceBefore=10, spaceAfter=4,
            leading=16, fontName="Helvetica-Bold",
        ),
        "paper_title": ParagraphStyle(
            "paper_title", parent=base["Normal"],
            fontSize=10.5, textColor=NAVY, fontName="Helvetica-Bold",
            spaceBefore=4, spaceAfter=2, leading=14,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base["Normal"],
            fontSize=8.5, textColor=MID_GREY, spaceAfter=4, leading=12,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontSize=9.5, textColor=HexColor("#374151"), alignment=TA_JUSTIFY,
            spaceAfter=3, leading=14,
        ),
        "label": ParagraphStyle(
            "label", parent=base["Normal"],
            fontSize=8.5, textColor=TEAL, fontName="Helvetica-Bold",
            spaceAfter=1, leading=12,
        ),
        "toc_entry": ParagraphStyle(
            "toc_entry", parent=base["Normal"],
            fontSize=10, textColor=NAVY, spaceAfter=3, leading=14,
        ),
        "highlight_title": ParagraphStyle(
            "highlight_title", parent=base["Normal"],
            fontSize=10, textColor=NAVY, fontName="Helvetica-Bold",
            spaceAfter=2, leading=13,
        ),
        "highlight_body": ParagraphStyle(
            "highlight_body", parent=base["Normal"],
            fontSize=9, textColor=HexColor("#374151"), leading=13,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"],
            fontSize=7.5, textColor=MID_GREY, alignment=TA_CENTER,
        ),
    }
    return styles


# ── Page templates ─────────────────────────────────────────────────────────────

class DigestDoc(SimpleDocTemplate):
    def __init__(self, filename, metadata):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=MARGIN, bottomMargin=20 * mm,
        )
        self.metadata = metadata

    def handle_pageEnd(self):
        self._drawFooter()
        super().handle_pageEnd()

    def _drawFooter(self):
        c = self.canv
        c.saveState()
        c.setFillColor(MID_GREY)
        c.setFont("Helvetica", 7.5)
        page_num = c.getPageNumber()
        footer_text = (
            f"GI Research Digest  |  Week ending {datetime.now().strftime('%d %B %Y')}"
            f"  |  Page {page_num}"
        )
        c.drawCentredString(W / 2, 13 * mm, footer_text)
        c.setStrokeColor(LIGHT_GREY)
        c.line(MARGIN, 17 * mm, W - MARGIN, 17 * mm)
        c.restoreState()


# ── Content builders ───────────────────────────────────────────────────────────

def cover_page(styles, metadata):
    """Returns flowables for the cover page."""
    elements = []
    elements.append(Spacer(1, 40 * mm))

    # Navy banner
    banner_data = [[Paragraph("GI Research Digest", styles["cover_title"])]]
    banner = Table(banner_data, colWidths=[W - 2 * MARGIN])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [6, 6, 0, 0]),
    ]))
    elements.append(banner)

    # Teal sub-banner
    end_date = datetime.now()
    start_date = end_date - timedelta(days=metadata.get("period_days", 7))
    date_str = f"{start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')}"
    sub_data = [[Paragraph(f"Weekly Literature Review  |  {date_str}", styles["cover_sub"])]]
    sub = Table(sub_data, colWidths=[W - 2 * MARGIN])
    sub.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TEAL),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [0, 0, 6, 6]),
    ]))
    elements.append(sub)
    elements.append(Spacer(1, 20 * mm))

    # Stats boxes
    hep_count = metadata.get("hep_count", 0)
    gi_count = metadata.get("gi_count", 0)
    total = metadata.get("total_fetched", 0)

    stats = [
        [
            _stat_box(str(hep_count), "Hepatology", LIGHT_TEAL, TEAL),
            _stat_box(str(gi_count), "Luminal / HPB / Endo", LIGHT_GOLD, GOLD),
            _stat_box(str(hep_count + gi_count), "Total papers", LIGHT_GREY, NAVY),
        ]
    ]
    stats_table = Table(stats, colWidths=[(W - 2 * MARGIN) / 3] * 3, hAlign="CENTER")
    stats_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 16 * mm))

    # Journals covered
    journal_note = (
        "<b>Journals covered:</b> Gut · Frontline Gastroenterology · BMJ Open Gastroenterology · "
        "Gastroenterology · Am J Gastroenterology · CGH · NEJM · The Lancet · "
        "Lancet Gastroenterology &amp; Hepatology · BMJ · Nature Medicine · "
        "Journal of Hepatology · JHEP Reports · Hepatology · Liver International · "
        "AP&amp;T · UEG Journal · Colorectal Disease · Endoscopy · Endoscopy International Open"
    )
    elements.append(Paragraph(journal_note, ParagraphStyle(
        "jnote", fontSize=8, textColor=MID_GREY, alignment=TA_CENTER, leading=13
    )))
    elements.append(Spacer(1, 8 * mm))

    disclaimer = (
        "<i>This digest is AI-generated from PubMed abstracts for educational purposes only. "
        "It does not constitute clinical advice. Always consult full-text articles before "
        "applying findings to patient care.</i>"
    )
    elements.append(Paragraph(disclaimer, ParagraphStyle(
        "disc", fontSize=8, textColor=MID_GREY, alignment=TA_CENTER,
        leading=12, borderColor=LIGHT_GREY
    )))
    elements.append(PageBreak())
    return elements


def _stat_box(value, label, bg, fg):
    """Returns a Table cell with a coloured stat box."""
    data = [
        [Paragraph(f"<b>{value}</b>", ParagraphStyle("sv", fontSize=24, textColor=fg,
                                                       alignment=TA_CENTER))],
        [Paragraph(label, ParagraphStyle("sl", fontSize=8.5, textColor=fg,
                                          alignment=TA_CENTER))],
    ]
    t = Table(data, colWidths=[50 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [6, 6, 6, 6]),
    ]))
    return t


def section_header_block(title, subtitle, colour):
    """Coloured section header banner."""
    data = [[
        Paragraph(title, ParagraphStyle(
            "sh", fontSize=18, textColor=WHITE, fontName="Helvetica-Bold",
            leading=22
        )),
        Paragraph(subtitle, ParagraphStyle(
            "ss", fontSize=9, textColor=HexColor("#BDD6E6"), alignment=TA_RIGHT,
            leading=13
        )),
    ]]
    t = Table(data, colWidths=[100 * mm, W - 2 * MARGIN - 100 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colour),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (0, -1), 14),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 14),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [6, 6, 6, 6]),
    ]))
    return t


def highlights_box(papers, styles, colour, bg):
    """Top 3 highlights box for a section."""
    high_quality = [p for p in papers if p.get("quality_flag") == "high"][:3]
    if not high_quality:
        high_quality = papers[:3]

    elements = []
    title_data = [[Paragraph("⭐  Top Highlights This Week", ParagraphStyle(
        "ht", fontSize=10.5, textColor=colour, fontName="Helvetica-Bold"
    ))]]
    title_row = Table(title_data, colWidths=[W - 2 * MARGIN])
    title_row.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [6, 6, 0, 0]),
    ]))
    elements.append(title_row)

    rows = []
    for p in high_quality:
        bullet = f"<b>{p.get('subcategory','')}</b>  {p.get('headline','')}"
        rows.append([Paragraph(bullet, styles["highlight_body"])])

    content = Table(rows, colWidths=[W - 2 * MARGIN])
    content.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [0, 0, 6, 6]),
    ]))
    elements.append(content)
    return elements


def paper_card(paper, styles):
    """Returns a KeepTogether block for a single paper."""
    elements = []

    # Quality badge
    qf = paper.get("quality_flag", "moderate")
    q_colour, q_label = QUALITY_COLOURS.get(qf, (AMBER_FLAG, "● Moderate"))
    badge_style = ParagraphStyle("badge", fontSize=7.5, textColor=q_colour,
                                  fontName="Helvetica-Bold")

    # Header row: subcategory tag + quality badge
    header_data = [[
        Paragraph(f"[{paper.get('subcategory', '')}]", ParagraphStyle(
            "tag", fontSize=8, textColor=TEAL, fontName="Helvetica-Bold"
        )),
        Paragraph(q_label, badge_style),
    ]]
    header = Table(header_data, colWidths=[90 * mm, W - 2 * MARGIN - 90 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elements.append(header)

    # Title
    elements.append(Paragraph(paper.get("title", ""), styles["paper_title"]))

    # Meta line
    meta = f"{paper.get('authors','')}  ·  <i>{paper.get('journal','')}</i>  ·  {paper.get('pub_date','')}  ·  {paper.get('study_type','')}"
    elements.append(Paragraph(meta, styles["meta"]))

    # Headline
    elements.append(Paragraph(
        f"<b>Finding:</b>  {paper.get('headline', '')}",
        styles["body"]
    ))

    # Key findings
    if paper.get("key_findings"):
        elements.append(Paragraph("<b>Key findings:</b>", styles["label"]))
        elements.append(Paragraph(paper["key_findings"], styles["body"]))

    # Clinical relevance
    if paper.get("clinical_relevance"):
        elements.append(Paragraph("<b>Clinical relevance:</b>", styles["label"]))
        elements.append(Paragraph(paper["clinical_relevance"], styles["body"]))

    # PubMed link
    elements.append(Paragraph(
        f'<link href="{paper.get("url","")}" color="#0B7285">View on PubMed ↗</link>',
        ParagraphStyle("link", fontSize=8.5, textColor=TEAL, spaceAfter=6)
    ))

    # Divider
    elements.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GREY, spaceAfter=6))

    return KeepTogether(elements)


def practice_changing_card(paper, styles):
    """
    Renders a gold-bordered 'Practice Changing' banner card for landmark papers.
    Inserted above the standard paper_card.
    """
    elements = []

    # Gold header banner
    banner_text = "★★★  PRACTICE CHANGING  ★★★"
    banner_data = [[Paragraph(banner_text, ParagraphStyle(
        "pc_banner", fontSize=10, textColor=WHITE, fontName="Helvetica-Bold",
        alignment=TA_CENTER, leading=14
    ))]]
    banner = Table(banner_data, colWidths=[W - 2 * MARGIN])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [6, 6, 0, 0]),
    ]))
    elements.append(banner)

    # Gold-bordered content box
    content_rows = []

    # Title row
    content_rows.append([Paragraph(
        paper.get("title", ""),
        ParagraphStyle("pc_title", fontSize=10.5, textColor=DARK_GOLD,
                       fontName="Helvetica-Bold", leading=14, spaceAfter=2)
    )])

    # Meta
    meta = (f"{paper.get('authors','')}  ·  <i>{paper.get('journal','')}</i>  ·  "
            f"{paper.get('pub_date','')}  ·  {paper.get('study_type','')}")
    content_rows.append([Paragraph(meta, ParagraphStyle(
        "pc_meta", fontSize=8.5, textColor=MID_GREY, leading=12, spaceAfter=5
    ))])

    # Headline finding
    content_rows.append([Paragraph(
        f"<b>Finding:</b>  {paper.get('headline','')}",
        ParagraphStyle("pc_body", fontSize=9.5, textColor=HexColor("#374151"),
                       leading=14, spaceAfter=4, alignment=TA_JUSTIFY)
    )])

    # Key findings
    if paper.get("key_findings"):
        content_rows.append([Paragraph(
            "<b>Key findings:</b>",
            ParagraphStyle("pc_lbl", fontSize=8.5, textColor=GOLD,
                           fontName="Helvetica-Bold", leading=12, spaceAfter=1)
        )])
        content_rows.append([Paragraph(
            paper["key_findings"],
            ParagraphStyle("pc_body2", fontSize=9.5, textColor=HexColor("#374151"),
                           leading=14, spaceAfter=4, alignment=TA_JUSTIFY)
        )])

    # Practice-changing rationale — the special box-within-box
    if paper.get("practice_changing_reason"):
        reason_data = [[Paragraph(
            f"<b>Why this changes practice:</b>  {paper['practice_changing_reason']}",
            ParagraphStyle("pc_reason", fontSize=9.5, textColor=DEEP_GOLD,
                           leading=14, alignment=TA_JUSTIFY)
        )]]
        reason_box = Table(reason_data, colWidths=[W - 2 * MARGIN - 28])
        reason_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GOLD),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("ROUNDEDCORNERS", (0, 0), (-1, -1), [4, 4, 4, 4]),
        ]))
        content_rows.append([reason_box])

    # PubMed link
    content_rows.append([Paragraph(
        f'<link href="{paper.get("url","")}" color="#C8860A">View on PubMed ↗</link>',
        ParagraphStyle("pc_link", fontSize=8.5, textColor=GOLD, spaceAfter=2)
    )])

    content = Table(content_rows, colWidths=[W - 2 * MARGIN])
    content.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FFFDF5")),
        ("BOX", (0, 0), (-1, -1), 1.5, GOLD),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [0, 0, 6, 6]),
    ]))
    elements.append(content)
    elements.append(Spacer(1, 6))

    return KeepTogether(elements)


def guideline_card(guideline, styles):
    """Renders a card for a new society guideline."""
    elements = []

    # Society badge + title row
    header_data = [[
        Paragraph(
            f"[{guideline.get('subcategory', 'Guideline')}]",
            ParagraphStyle("gl_tag", fontSize=8, textColor=NAVY,
                           fontName="Helvetica-Bold")
        ),
        Paragraph("📋 New Guideline", ParagraphStyle(
            "gl_badge", fontSize=8, textColor=NAVY,
            fontName="Helvetica-Bold", alignment=TA_RIGHT
        )),
    ]]
    header = Table(header_data, colWidths=[90 * mm, W - 2 * MARGIN - 90 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elements.append(header)

    elements.append(Paragraph(guideline.get("title", ""), styles["paper_title"]))

    meta = (f"{guideline.get('authors','')}  ·  <i>{guideline.get('journal','')}</i>  ·  "
            f"{guideline.get('pub_date','')}")
    elements.append(Paragraph(meta, styles["meta"]))

    if guideline.get("headline"):
        elements.append(Paragraph(
            f"<b>Summary:</b>  {guideline['headline']}", styles["body"]
        ))
    if guideline.get("key_findings"):
        elements.append(Paragraph("<b>Key recommendations:</b>", styles["label"]))
        elements.append(Paragraph(guideline["key_findings"], styles["body"]))
    if guideline.get("clinical_relevance"):
        elements.append(Paragraph("<b>Clinical relevance:</b>", styles["label"]))
        elements.append(Paragraph(guideline["clinical_relevance"], styles["body"]))

    elements.append(Paragraph(
        f'<link href="{guideline.get("url","")}" color="#0B7285">View on PubMed ↗</link>',
        ParagraphStyle("link", fontSize=8.5, textColor=TEAL, spaceAfter=6)
    ))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT_GREY, spaceAfter=6))

    return KeepTogether(elements)


def guidelines_section(guidelines, styles):
    """Full guidelines section block."""
    elements = []
    elements.append(PageBreak())

    # Section header — deep navy/purple to distinguish
    GUIDELINE_COLOUR = HexColor("#3B1F6B")
    header_data = [[
        Paragraph("Section 3: New Society Guidelines", ParagraphStyle(
            "gh", fontSize=18, textColor=WHITE, fontName="Helvetica-Bold", leading=22
        )),
        Paragraph(f"{len(guidelines)} guideline{'s' if len(guidelines) != 1 else ''}",
                  ParagraphStyle("gs", fontSize=9, textColor=HexColor("#C4B5FD"),
                                 alignment=TA_RIGHT, leading=13)),
    ]]
    header = Table(header_data, colWidths=[100 * mm, W - 2 * MARGIN - 100 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GUIDELINE_COLOUR),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (0, -1), 14),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 14),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [6, 6, 6, 6]),
    ]))
    elements.append(header)
    elements.append(Spacer(1, 6 * mm))

    # Intro note
    elements.append(Paragraph(
        "The following clinical practice guidelines, position statements, and consensus "
        "documents were published this week by recognised gastroenterology and hepatology "
        "societies (BSG, NICE, EASL, AASLD, AGA, ACG, ESGE, ECCO, UEG, ACPGBI, ASGE).",
        ParagraphStyle("gl_intro", fontSize=9, textColor=MID_GREY, leading=13,
                       spaceAfter=10, alignment=TA_JUSTIFY)
    ))

    for g in guidelines:
        elements.append(guideline_card(g, styles))

    return elements


def group_by_subcategory(papers):
    """Group papers dict by subcategory."""
    groups = {}
    for p in papers:
        sc = p.get("subcategory", "Other")
        groups.setdefault(sc, []).append(p)
    return groups


def render_papers(papers, story, styles):
    """Render a section's papers: practice-changing gold cards first, then regular grouped cards."""
    pc_papers = [p for p in papers if p.get("practice_changing")]
    regular_papers = [p for p in papers if not p.get("practice_changing")]

    if pc_papers:
        story.append(Spacer(1, 4 * mm))
        for paper in pc_papers:
            story.append(practice_changing_card(paper, styles))
        story.append(Spacer(1, 4 * mm))

    groups = group_by_subcategory(regular_papers)
    for subcategory, grp_papers in sorted(groups.items()):
        story.append(Paragraph(subcategory, styles["subsection"]))
        story.append(HRFlowable(width="100%", thickness=1, color=TEAL, spaceAfter=4))
        for paper in grp_papers:
            story.append(paper_card(paper, styles))


# ── Main PDF builder ───────────────────────────────────────────────────────────

def generate_pdf(digest_data: dict, output_path: str) -> str:
    """
    Generate the weekly PDF digest.
    digest_data: output from fetch_and_summarise.run_digest()
    output_path: file path for the PDF
    Returns the output path.
    """
    styles = build_styles()
    hepatology = digest_data.get("hepatology", [])
    hepatology = digest_data.get("hepatology", [])
    luminal    = digest_data.get("luminal", [])
    hpb        = digest_data.get("hpb", [])
    endoscopy  = digest_data.get("endoscopy", [])
    guidelines = digest_data.get("guidelines", [])
    metadata   = digest_data.get("metadata", {})
    metadata["hep_count"] = len(hepatology)
    metadata["gi_count"]  = len(luminal) + len(hpb) + len(endoscopy)

    doc = DigestDoc(output_path, metadata)
    story = []

    # ── Cover ──────────────────────────────────────────────────────────────────
    story.extend(cover_page(styles, metadata))

    # ── Section 1: Hepatology ──────────────────────────────────────────────────
    story.append(section_header_block("Section 1: Hepatology", f"{len(hepatology)} papers", NAVY))
    story.append(Spacer(1, 6 * mm))
    if hepatology:
        story.extend(highlights_box(hepatology, styles, NAVY, LIGHT_TEAL))
        story.append(Spacer(1, 8 * mm))
        render_papers(hepatology, story, styles)
    else:
        story.append(Paragraph("No hepatology papers found this week.", styles["body"]))
    story.append(PageBreak())

    # ── Section 2: Luminal Gastroenterology ───────────────────────────────────
    story.append(section_header_block("Section 2: Luminal Gastroenterology", f"{len(luminal)} papers", TEAL))
    story.append(Spacer(1, 6 * mm))
    if luminal:
        story.extend(highlights_box(luminal, styles, TEAL, LIGHT_GOLD))
        story.append(Spacer(1, 8 * mm))
        render_papers(luminal, story, styles)
    else:
        story.append(Paragraph("No luminal gastroenterology papers found this week.", styles["body"]))
    story.append(PageBreak())

    # ── Section 3: HPB ────────────────────────────────────────────────────────
    HPB_COLOUR = HexColor("#1F5C3A")
    HPB_LIGHT  = HexColor("#E8F5EE")
    story.append(section_header_block("Section 3: Hepatopancreatobiliary (HPB)", f"{len(hpb)} papers", HPB_COLOUR))
    story.append(Spacer(1, 6 * mm))
    if hpb:
        story.extend(highlights_box(hpb, styles, HPB_COLOUR, HPB_LIGHT))
        story.append(Spacer(1, 8 * mm))
        render_papers(hpb, story, styles)
    else:
        story.append(Paragraph("No HPB papers found this week.", styles["body"]))
    story.append(PageBreak())

    # ── Section 4: Endoscopy ──────────────────────────────────────────────────
    ENDO_COLOUR = HexColor("#6B3FA0")
    ENDO_LIGHT  = HexColor("#F3EEFF")
    story.append(section_header_block("Section 4: Endoscopy", f"{len(endoscopy)} papers", ENDO_COLOUR))
    story.append(Spacer(1, 6 * mm))
    if endoscopy:
        story.extend(highlights_box(endoscopy, styles, ENDO_COLOUR, ENDO_LIGHT))
        story.append(Spacer(1, 8 * mm))
        render_papers(endoscopy, story, styles)
    else:
        story.append(Paragraph("No endoscopy papers found this week.", styles["body"]))

    # ── Section 5: Guidelines ─────────────────────────────────────────────────
    story.append(PageBreak())
    story.extend(guidelines_section(guidelines, styles))
    if not guidelines:
        story.append(Paragraph(
            "No new society guidelines were identified in the target journals this week.",
            styles["body"]
        ))

    # ── Build ──────────────────────────────────────────────────────────────────
    doc.build(story)
    print(f"✅ PDF written to: {output_path}")
    return output_path
