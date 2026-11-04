"""
generate_pdf.py
Generates a clean, professional PDF digest from the summarised paper data.
Uses ReportLab Platypus for flowing multi-page layout.
Styled with the Rex Hepatis (rexhepatis.org) brand: navy, blue and gold,
Newsreader headings, IBM Plex Sans text, and the crown logo.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Image
)
from reportlab.lib.colors import HexColor
from datetime import datetime, timedelta
from xml.sax.saxutils import escape
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping

# ── Rex Hepatis brand ──────────────────────────────────────────────────────────
ASSETS     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
CROWN_PATH = os.path.join(ASSETS, "brand", "crown.png")
CROWN_RATIO = 186 / 274          # height / width of crown.png
SITE_URL   = "https://rexhepatis.org"

# Colours taken from rexhepatis.org's stylesheet
NAVY       = HexColor("#0E1A2E")   # --navy
NAVY_2     = HexColor("#13223A")   # --navy-2
BLUE       = HexColor("#2C6DBA")   # --acc
BLUE_LT    = HexColor("#6FA8EC")   # --acc-lt
LIGHT_BLUE = HexColor("#EBF2FB")
GOLD       = HexColor("#C99A2E")   # --gold
DARK_GOLD  = HexColor("#7C560E")   # crown shadow
LIGHT_GOLD = HexColor("#FBF5E6")
DEEP_GOLD  = HexColor("#6E4B0B")
MID_GREY   = HexColor("#4A5872")   # --ink-2
BODY_INK   = HexColor("#33415C")
RULE       = HexColor("#D5DCE8")   # --rule
LIGHT_GREY = HexColor("#F3F5F9")
RED_FLAG   = HexColor("#C0262D")
GREEN_FLAG = HexColor("#1E8A4C")
AMBER_FLAG = HexColor("#B7791F")
WHITE      = colors.white
BLACK      = colors.black

# Fonts (SIL Open Font License, see assets/fonts/OFL-*.txt)
SANS        = "Plex"
SANS_BOLD   = "Plex-SemiBold"
SERIF       = "Newsreader"
SERIF_ITAL  = "Newsreader-Italic"
for _name, _file in [
    (SANS, "IBMPlexSans-Regular.ttf"),
    (SANS_BOLD, "IBMPlexSans-SemiBold.ttf"),
    ("Plex-Italic", "IBMPlexSans-Italic.ttf"),
    ("Plex-SemiBoldItalic", "IBMPlexSans-SemiBoldItalic.ttf"),
    (SERIF, "Newsreader-SemiBold.ttf"),
    (SERIF_ITAL, "Newsreader-Italic.ttf"),
]:
    pdfmetrics.registerFont(TTFont(_name, os.path.join(ASSETS, "fonts", _file)))
# So <b> and <i> inside a paragraph pick the right Plex / Newsreader face
for _fam, _n, _b, _i, _bi in [
    (SANS, SANS, SANS_BOLD, "Plex-Italic", "Plex-SemiBoldItalic"),
    (SANS_BOLD, SANS, SANS_BOLD, "Plex-Italic", "Plex-SemiBoldItalic"),
    (SERIF, SERIF, SERIF, SERIF_ITAL, SERIF_ITAL),
]:
    addMapping(_fam, 0, 0, _n)
    addMapping(_fam, 1, 0, _b)
    addMapping(_fam, 0, 1, _i)
    addMapping(_fam, 1, 1, _bi)
# Styles created without a parent default to Plex instead of Helvetica
ParagraphStyle.defaults["fontName"] = SANS
ParagraphStyle.defaults["bulletFontName"] = SANS


def crown(height: float) -> str:
    """Inline crown logo for use inside a Paragraph."""
    width = height / CROWN_RATIO
    return f'<img src="{CROWN_PATH}" width="{width:.1f}" height="{height:.1f}" valign="middle"/>'

W, H = A4
MARGIN = 18 * mm

# The brand fonts have no dot glyph for the quality badges. Embed DejaVu Sans
# for it when the system has it (GitHub's Ubuntu runners do); otherwise leave
# it out rather than print a black box.
_SYMBOL_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/DejaVuSans.ttf",
]


def _symbol(char: str) -> str:
    return f'<font name="SymbolFont">{char}</font>' if _HAS_SYMBOL_FONT else ""


_HAS_SYMBOL_FONT = False
for _path in _SYMBOL_FONT_PATHS:
    if os.path.exists(_path):
        pdfmetrics.registerFont(TTFont("SymbolFont", _path))
        _HAS_SYMBOL_FONT = True
        break

DOT  = _symbol("●")

QUALITY_COLOURS = {
    "high":        (GREEN_FLAG, f"{DOT} High Quality"),
    "moderate":    (AMBER_FLAG, f"{DOT} Moderate"),
    "preliminary": (RED_FLAG,   f"{DOT} Preliminary"),
}


def esc(value) -> str:
    """Escape text from PubMed or the model for ReportLab's mini-markup.

    Unescaped, "p<0.001" or "R&D" is read as markup: text is silently dropped
    or mangled, and some strings (e.g. "<b") crash the whole PDF build.
    """
    return escape(str(value or ""))


# ── Style sheet ────────────────────────────────────────────────────────────────

def build_styles():
    base = getSampleStyleSheet()

    styles = {
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontName=SERIF,
            fontSize=34, textColor=WHITE, alignment=TA_LEFT,
            spaceAfter=0, leading=40,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontName=SANS,
            fontSize=12, textColor=HexColor("#C9D4E5"), alignment=TA_LEFT,
            spaceAfter=0, leading=16,
        ),
        "cover_date": ParagraphStyle(
            "cover_date", parent=base["Normal"], fontName=SANS,
            fontSize=11, textColor=BLUE_LT, alignment=TA_CENTER,
        ),
        "section_header": ParagraphStyle(
            "section_header", parent=base["Heading1"], fontName=SERIF,
            fontSize=18, textColor=WHITE, alignment=TA_LEFT,
            spaceAfter=0, spaceBefore=0, leading=22,
        ),
        "subsection": ParagraphStyle(
            "subsection", parent=base["Heading2"],
            fontSize=12, textColor=BLUE, spaceBefore=10, spaceAfter=4,
            leading=16, fontName=SANS_BOLD,
        ),
        "paper_title": ParagraphStyle(
            "paper_title", parent=base["Normal"],
            fontSize=10.5, textColor=NAVY, fontName=SANS_BOLD,
            spaceBefore=4, spaceAfter=2, leading=14,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base["Normal"], fontName=SANS,
            fontSize=8.5, textColor=MID_GREY, spaceAfter=4, leading=12,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName=SANS,
            fontSize=9.5, textColor=BODY_INK, alignment=TA_JUSTIFY,
            spaceAfter=3, leading=14,
        ),
        "label": ParagraphStyle(
            "label", parent=base["Normal"],
            fontSize=8.5, textColor=BLUE, fontName=SANS_BOLD,
            spaceAfter=1, leading=12,
        ),
        "toc_entry": ParagraphStyle(
            "toc_entry", parent=base["Normal"], fontName=SANS,
            fontSize=10, textColor=NAVY, spaceAfter=3, leading=14,
        ),
        "highlight_title": ParagraphStyle(
            "highlight_title", parent=base["Normal"],
            fontSize=10, textColor=NAVY, fontName=SANS_BOLD,
            spaceAfter=2, leading=13,
        ),
        "highlight_body": ParagraphStyle(
            "highlight_body", parent=base["Normal"], fontName=SANS,
            fontSize=9, textColor=BODY_INK, leading=13,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"], fontName=SANS,
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
        page_num = c.getPageNumber()
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(MARGIN, 17 * mm, W - MARGIN, 17 * mm)
        # Left: crown + "Rex Hepatis"; right: date and page number
        crown_h = 3.2 * mm
        c.drawImage(CROWN_PATH, MARGIN, 11.6 * mm, width=crown_h / CROWN_RATIO,
                    height=crown_h, mask="auto")
        x = MARGIN + crown_h / CROWN_RATIO + 1.5 * mm
        c.setFillColor(NAVY)
        c.setFont(SERIF, 8.5)
        c.drawString(x, 12.4 * mm, "Rex Hepatis")
        x += pdfmetrics.stringWidth("Rex Hepatis", SERIF, 8.5) + 3 * mm
        c.setFillColor(MID_GREY)
        c.setFont(SANS, 7.5)
        c.drawString(x, 12.4 * mm, "GI Research Digest  ·  rexhepatis.org")
        c.drawRightString(
            W - MARGIN, 12.4 * mm,
            f"Week ending {datetime.now().strftime('%d %B %Y')}  |  Page {page_num}",
        )
        c.restoreState()


# ── Content builders ───────────────────────────────────────────────────────────

def cover_page(styles, metadata):
    """Returns flowables for the cover page."""
    elements = []
    elements.append(Spacer(1, 22 * mm))

    # Crown logo and "Rex Hepatis" wordmark
    logo_w = 30 * mm
    elements.append(Image(CROWN_PATH, width=logo_w, height=logo_w * CROWN_RATIO))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph("Rex Hepatis", ParagraphStyle(
        "brand", fontName=SERIF, fontSize=22, leading=26, textColor=NAVY, alignment=TA_CENTER
    )))
    elements.append(Paragraph("Hepatobiliary learning, made accessible", ParagraphStyle(
        "tagline", fontName=SERIF_ITAL, fontSize=11, leading=15, textColor=MID_GREY,
        alignment=TA_CENTER
    )))
    elements.append(Spacer(1, 12 * mm))

    # Navy title block with the site's blue accent rule
    end_date = datetime.now()
    start_date = end_date - timedelta(days=metadata.get("period_days", 7))
    date_str = f"{start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')}"
    banner = Table([
        [Paragraph("GI Research Digest", styles["cover_title"])],
        [Paragraph(f"Weekly literature review  ·  {date_str}", styles["cover_sub"])],
    ], colWidths=[W - 2 * MARGIN])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LINEBEFORE", (0, 0), (0, -1), 4, BLUE),
        ("LINEBELOW", (0, -1), (-1, -1), 3, BLUE),
        ("TOPPADDING", (0, 0), (-1, 0), 22),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 22),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
    ]))
    elements.append(banner)
    elements.append(Spacer(1, 14 * mm))

    # Stats boxes
    hep_count = metadata.get("hep_count", 0)
    gi_count = metadata.get("gi_count", 0)
    total = metadata.get("total_fetched", 0)

    stats = [
        [
            _stat_box(str(hep_count), "Hepatology", LIGHT_BLUE, BLUE),
            _stat_box(str(gi_count), "Luminal / HPB / Endo", LIGHT_GOLD, DARK_GOLD),
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
        leading=12
    )))
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(
        f'More hepatobiliary teaching at <link href="{SITE_URL}" color="#2C6DBA">'
        f'<b>rexhepatis.org</b></link>',
        ParagraphStyle("site", fontSize=9, textColor=MID_GREY, alignment=TA_CENTER, leading=13)
    ))
    elements.append(PageBreak())
    return elements


def _stat_box(value, label, bg, fg):
    """Returns a Table cell with a coloured stat box."""
    data = [
        [Paragraph(value, ParagraphStyle("sv", fontName=SERIF, fontSize=26, leading=30,
                                         textColor=fg, alignment=TA_CENTER))],
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
            "sh", fontSize=18, textColor=WHITE, fontName=SERIF,
            leading=22
        )),
        Paragraph(subtitle, ParagraphStyle(
            "ss", fontSize=9, textColor=HexColor("#C9D4E5"), alignment=TA_RIGHT,
            leading=13
        )),
    ]]
    t = Table(data, colWidths=[100 * mm, W - 2 * MARGIN - 100 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colour),
        ("LINEBEFORE", (0, 0), (0, -1), 4, BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (0, -1), 14),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 14),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def highlights_box(papers, styles, colour, bg):
    """Top 3 highlights box for a section."""
    high_quality = [p for p in papers if p.get("quality_flag") == "high"][:3]
    if not high_quality:
        high_quality = papers[:3]

    elements = []
    title_data = [[Paragraph(f"{crown(11)}&nbsp;&nbsp;Top Highlights This Week", ParagraphStyle(
        "ht", fontSize=10.5, textColor=colour, fontName=SANS_BOLD
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
        bullet = f"<b>{esc(p.get('subcategory'))}</b>  {esc(p.get('headline'))}"
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
    q_colour, q_label = QUALITY_COLOURS.get(qf, QUALITY_COLOURS["moderate"])
    badge_style = ParagraphStyle("badge", fontSize=7.5, textColor=q_colour,
                                  fontName=SANS_BOLD, alignment=TA_RIGHT)

    # Header row: subcategory tag + quality badge
    header_data = [[
        Paragraph(f"[{esc(paper.get('subcategory'))}]", ParagraphStyle(
            "tag", fontSize=8, textColor=BLUE, fontName=SANS_BOLD
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
    elements.append(Paragraph(esc(paper.get("title")), styles["paper_title"]))

    # Meta line
    meta = (f"{esc(paper.get('authors'))}  ·  <i>{esc(paper.get('journal'))}</i>  ·  "
            f"{esc(paper.get('pub_date'))}  ·  {esc(paper.get('study_type'))}")
    elements.append(Paragraph(meta, styles["meta"]))

    # Headline
    elements.append(Paragraph(
        f"<b>Finding:</b>  {esc(paper.get('headline'))}",
        styles["body"]
    ))

    # Key findings
    if paper.get("key_findings"):
        elements.append(Paragraph("<b>Key findings:</b>", styles["label"]))
        elements.append(Paragraph(esc(paper["key_findings"]), styles["body"]))

    # Clinical relevance
    if paper.get("clinical_relevance"):
        elements.append(Paragraph("<b>Clinical relevance:</b>", styles["label"]))
        elements.append(Paragraph(esc(paper["clinical_relevance"]), styles["body"]))

    # PubMed link
    elements.append(Paragraph(
        f'<link href="{esc(paper.get("url"))}" color="#2C6DBA">View on PubMed &gt;</link>',
        ParagraphStyle("link", fontSize=8.5, textColor=BLUE, spaceAfter=6)
    ))

    # Divider
    elements.append(HRFlowable(width="100%", thickness=0.5, color=RULE, spaceAfter=6))

    return KeepTogether(elements)


def practice_changing_card(paper, styles):
    """
    Renders a gold-bordered 'Notable' banner card for landmark papers.
    Inserted above the standard paper_card.
    """
    elements = []

    # Navy header banner with the gold crown
    banner_text = f"{crown(13)}&nbsp;&nbsp;&nbsp;NOTABLE&nbsp;&nbsp;&nbsp;{crown(13)}"
    banner_data = [[Paragraph(banner_text, ParagraphStyle(
        "pc_banner", fontSize=10.5, textColor=GOLD, fontName=SANS_BOLD,
        alignment=TA_CENTER, leading=16
    ))]]
    banner = Table(banner_data, colWidths=[W - 2 * MARGIN])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("BOX", (0, 0), (-1, -1), 1.5, GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [6, 6, 0, 0]),
    ]))
    elements.append(banner)

    # Gold-bordered content box
    content_rows = []

    # Title row
    content_rows.append([Paragraph(
        esc(paper.get("title")),
        ParagraphStyle("pc_title", fontSize=10.5, textColor=DARK_GOLD,
                       fontName=SANS_BOLD, leading=14, spaceAfter=2)
    )])

    # Meta
    meta = (f"{esc(paper.get('authors'))}  ·  <i>{esc(paper.get('journal'))}</i>  ·  "
            f"{esc(paper.get('pub_date'))}  ·  {esc(paper.get('study_type'))}")
    content_rows.append([Paragraph(meta, ParagraphStyle(
        "pc_meta", fontSize=8.5, textColor=MID_GREY, leading=12, spaceAfter=5
    ))])

    # Headline finding
    content_rows.append([Paragraph(
        f"<b>Finding:</b>  {esc(paper.get('headline'))}",
        ParagraphStyle("pc_body", fontSize=9.5, textColor=BODY_INK,
                       leading=14, spaceAfter=4, alignment=TA_JUSTIFY)
    )])

    # Key findings
    if paper.get("key_findings"):
        content_rows.append([Paragraph(
            "<b>Key findings:</b>",
            ParagraphStyle("pc_lbl", fontSize=8.5, textColor=DARK_GOLD,
                           fontName=SANS_BOLD, leading=12, spaceAfter=1)
        )])
        content_rows.append([Paragraph(
            esc(paper["key_findings"]),
            ParagraphStyle("pc_body2", fontSize=9.5, textColor=BODY_INK,
                           leading=14, spaceAfter=4, alignment=TA_JUSTIFY)
        )])

    # Practice-changing rationale — the special box-within-box
    if paper.get("practice_changing_reason"):
        reason_data = [[Paragraph(
            f"<b>Why this is notable:</b>  {esc(paper['practice_changing_reason'])}",
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
        f'<link href="{esc(paper.get("url"))}" color="#7C560E">View on PubMed &gt;</link>',
        ParagraphStyle("pc_link", fontSize=8.5, textColor=DARK_GOLD, spaceAfter=2)
    )])

    content = Table(content_rows, colWidths=[W - 2 * MARGIN])
    content.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FFFDF7")),
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
            f"[{esc(guideline.get('subcategory') or 'Guideline')}]",
            ParagraphStyle("gl_tag", fontSize=8, textColor=NAVY,
                           fontName=SANS_BOLD)
        ),
        Paragraph("New Guideline", ParagraphStyle(
            "gl_badge", fontSize=8, textColor=NAVY,
            fontName=SANS_BOLD, alignment=TA_RIGHT
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

    elements.append(Paragraph(esc(guideline.get("title")), styles["paper_title"]))

    meta = (f"{esc(guideline.get('authors'))}  ·  <i>{esc(guideline.get('journal'))}</i>  ·  "
            f"{esc(guideline.get('pub_date'))}")
    elements.append(Paragraph(meta, styles["meta"]))

    if guideline.get("headline"):
        elements.append(Paragraph(
            f"<b>Summary:</b>  {esc(guideline['headline'])}", styles["body"]
        ))
    if guideline.get("key_findings"):
        elements.append(Paragraph("<b>Key recommendations:</b>", styles["label"]))
        elements.append(Paragraph(esc(guideline["key_findings"]), styles["body"]))
    if guideline.get("clinical_relevance"):
        elements.append(Paragraph("<b>Clinical relevance:</b>", styles["label"]))
        elements.append(Paragraph(esc(guideline["clinical_relevance"]), styles["body"]))

    elements.append(Paragraph(
        f'<link href="{esc(guideline.get("url"))}" color="#2C6DBA">View on PubMed &gt;</link>',
        ParagraphStyle("link", fontSize=8.5, textColor=BLUE, spaceAfter=6)
    ))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=RULE, spaceAfter=6))

    return KeepTogether(elements)


def guidelines_section(guidelines, styles):
    """Full guidelines section block."""
    elements = []

    elements.append(section_header_block(
        "Section 5: New Society Guidelines",
        f"{len(guidelines)} guideline{'s' if len(guidelines) != 1 else ''}",
        NAVY,
    ))
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
        story.append(Paragraph(esc(subcategory), styles["subsection"]))
        story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=4))
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
        story.extend(highlights_box(hepatology, styles, NAVY, LIGHT_BLUE))
        story.append(Spacer(1, 8 * mm))
        render_papers(hepatology, story, styles)
    else:
        story.append(Paragraph("No hepatology papers found this week.", styles["body"]))
    story.append(PageBreak())

    # ── Section 2: Luminal Gastroenterology ───────────────────────────────────
    story.append(section_header_block("Section 2: Luminal Gastroenterology", f"{len(luminal)} papers", NAVY))
    story.append(Spacer(1, 6 * mm))
    if luminal:
        story.extend(highlights_box(luminal, styles, NAVY, LIGHT_BLUE))
        story.append(Spacer(1, 8 * mm))
        render_papers(luminal, story, styles)
    else:
        story.append(Paragraph("No luminal gastroenterology papers found this week.", styles["body"]))
    story.append(PageBreak())

    # ── Section 3: HPB ────────────────────────────────────────────────────────
    story.append(section_header_block("Section 3: Hepatopancreatobiliary (HPB)", f"{len(hpb)} papers", NAVY))
    story.append(Spacer(1, 6 * mm))
    if hpb:
        story.extend(highlights_box(hpb, styles, NAVY, LIGHT_BLUE))
        story.append(Spacer(1, 8 * mm))
        render_papers(hpb, story, styles)
    else:
        story.append(Paragraph("No HPB papers found this week.", styles["body"]))
    story.append(PageBreak())

    # ── Section 4: Endoscopy ──────────────────────────────────────────────────
    story.append(section_header_block("Section 4: Endoscopy", f"{len(endoscopy)} papers", NAVY))
    story.append(Spacer(1, 6 * mm))
    if endoscopy:
        story.extend(highlights_box(endoscopy, styles, NAVY, LIGHT_BLUE))
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
