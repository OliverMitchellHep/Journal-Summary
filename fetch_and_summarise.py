"""
fetch_and_summarise.py
Fetches last 7 days of papers from PubMed across target GI/hepatology journals,
summarises each with Claude Sonnet 5.5, and returns structured data ready for PDF generation.

Paper limits: 10 hepatology+HPB, 5 luminal GI, 5 endoscopy = 20 total
Focus: clinical studies (RCTs, cohorts, meta-analyses). Molecular/basic science excluded.
"""

import requests
import anthropic
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Literal, Optional
from pydantic import BaseModel

# ── Journal list ───────────────────────────────────────────────────────────────
JOURNALS = [
    "Gut", "Frontline Gastroenterol", "BMJ Open Gastroenterol",
    "Gastroenterology", "Am J Gastroenterol", "Clin Gastroenterol Hepatol",
    "N Engl J Med", "Lancet", "Lancet Gastroenterol Hepatol", "BMJ", "Nat Med",
    "J Hepatol", "JHEP Rep", "Hepatology", "Liver Int", "Aliment Pharmacol Ther",
    "United European Gastroenterol J", "Colorectal Dis", "Endoscopy", "Endosc Int Open",
]

# ── Journal priority tiers (lower number = higher priority) ───────────────────
JOURNAL_PRIORITY = {
    "N Engl J Med": 1, "Lancet": 1, "Nat Med": 1, "BMJ": 1,
    "Gastroenterology": 1, "Gut": 1, "J Hepatol": 1,
    "Lancet Gastroenterol Hepatol": 1,
    "Am J Gastroenterol": 2, "Hepatology": 2, "JHEP Rep": 2,
    "Clin Gastroenterol Hepatol": 2, "Endoscopy": 2, "Aliment Pharmacol Ther": 2,
    "Frontline Gastroenterol": 3, "BMJ Open Gastroenterol": 3, "Liver Int": 3,
    "United European Gastroenterol J": 3, "Colorectal Dis": 3, "Endosc Int Open": 3,
}

UK_JOURNALS = {
    "Gut", "Frontline Gastroenterol", "BMJ Open Gastroenterol", "Lancet",
    "Lancet Gastroenterol Hepatol", "BMJ", "Aliment Pharmacol Ther", "Colorectal Dis",
}

# ── Paper limits per section ───────────────────────────────────────────────────
LIMITS = {
    "hepatology": 7,   # hepatology + HPB combined = 10
    "hpb":        3,
    "luminal":    5,
    "endoscopy":  5,
}

PUBMED_BASE     = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ANTHROPIC_MODEL = "claude-sonnet-5-5"


# ── PubMed helpers ─────────────────────────────────────────────────────────────

def build_query(days_back: int = 7) -> str:
    end   = datetime.today()
    start = end - timedelta(days=days_back)
    date_range     = f"{start.strftime('%Y/%m/%d')}:{end.strftime('%Y/%m/%d')}[dp]"
    journal_clause = " OR ".join([f'"{j}"[ta]' for j in JOURNALS])
    return f"({journal_clause}) AND {date_range}"


def search_pubmed(query: str, max_results: int = 2000) -> list[str]:
    # A week across these journals is typically 250-600 records, so the limit
    # must sit well above that: anything past it is dropped before the
    # journal-priority sort ever sees it.
    params = {
        "db": "pubmed", "term": query, "retmax": max_results, "retmode": "json",
    }
    r = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    return r.json()["esearchresult"]["idlist"]


def fetch_abstracts(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    # POST, not GET: several hundred IDs make the URL too long for a GET.
    data = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract"}
    r = requests.post(f"{PUBMED_BASE}/efetch.fcgi", data=data, timeout=120)
    r.raise_for_status()
    return parse_pubmed_xml(r.text)


def parse_pubmed_xml(xml_text: str) -> list[dict]:
    root     = ET.fromstring(xml_text)
    articles = []

    for article in root.findall(".//PubmedArticle"):
        try:
            medline = article.find("MedlineCitation")
            art     = medline.find("Article")

            title_el = art.find("ArticleTitle")
            title    = "".join(title_el.itertext()) if title_el is not None else "No title"

            abstract_texts = art.findall(".//AbstractText")
            abstract = " ".join("".join(a.itertext()) for a in abstract_texts) if abstract_texts else ""

            journal_abbr_el = art.find(".//Journal/ISOAbbreviation")
            journal_abbr    = journal_abbr_el.text if journal_abbr_el is not None else ""
            journal_full_el = art.find(".//Journal/Title")
            journal_full    = journal_full_el.text if journal_full_el is not None else journal_abbr
            # MedlineTA is the same abbreviation the [ta] search used, so it
            # matches the JOURNALS / JOURNAL_PRIORITY keys exactly.
            medline_ta = medline.findtext("MedlineJournalInfo/MedlineTA", "") or journal_abbr

            authors = []
            for author in art.findall(".//Author"):
                ln = author.find("LastName")
                fn = author.find("ForeName")
                if ln is not None and ln.text:
                    name = ln.text
                    if fn is not None and fn.text:
                        name += f" {fn.text[0]}"
                    authors.append(name)
            author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")

            pub_date     = medline.find(".//PubDate")
            pub_date_str = ""
            if pub_date is not None:
                pub_date_str = (f"{pub_date.findtext('Month', '')} {pub_date.findtext('Year', '')}".strip()
                                or pub_date.findtext("MedlineDate", ""))

            pmid_el = medline.find("PMID")
            pmid    = pmid_el.text if pmid_el is not None else ""

            doi = ""
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text
                    break

            # Skip letters, editorials, corrections
            pub_types  = [pt.text for pt in art.findall(".//PublicationType")]
            skip_types = {"Letter", "Editorial", "Retraction of Publication",
                          "Published Erratum", "Comment", "News"}
            if any(pt in skip_types for pt in pub_types):
                continue

            if len(abstract) < 100:
                continue

            # Journal priority scoring. Exact match: a substring match put every
            # title containing "Gastroenterology" or "BMJ" into the top tier.
            priority = JOURNAL_PRIORITY.get(medline_ta, 3)
            is_uk    = medline_ta in UK_JOURNALS

            articles.append({
                "pmid": pmid, "title": title, "authors": author_str,
                "journal": journal_full, "journal_abbr": journal_abbr,
                "pub_date": pub_date_str, "abstract": abstract[:3000],
                "doi": doi, "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "_priority": priority, "_is_uk": is_uk,
            })
        except Exception:
            continue

    # Sort: tier first, UK journals boosted by 0.5 within tier
    articles.sort(key=lambda x: x["_priority"] - (0.5 if x["_is_uk"] else 0))
    return articles


# ── Claude Sonnet summarisation ────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a specialist medical AI assistant helping a UK NHS consultant gastroenterologist 
stay up to date with research. You will be given a paper title and abstract.

Return JSON with this exact schema:
{
  "category": "hepatology" | "luminal" | "hpb" | "endoscopy" | "exclude" | "guideline",
  "subcategory": string,
  "headline": string,
  "key_findings": string,
  "clinical_relevance": string,
  "study_type": string,
  "quality_flag": "high" | "moderate" | "preliminary",
  "practice_changing": true | false,
  "practice_changing_reason": string
}

CATEGORY RULES — assign ONE category only:
- "hepatology": liver parenchymal disease — NAFLD/MASLD, MASH, cirrhosis, portal hypertension,
  viral hepatitis (HBV/HCV/HDV/HEV), alcohol-related liver disease, autoimmune hepatitis,
  PBC, PSC, liver transplantation, HCC
- "luminal": luminal GI disease — IBD (Crohn's, UC), colorectal cancer, IBS, coeliac disease,
  motility disorders, upper GI (oesophagus, stomach, small bowel), gut microbiome
- "hpb": hepatopancreatobiliary — pancreatic cancer, pancreatitis, pancreatic cysts,
  biliary tract cancer, cholangiocarcinoma, gallbladder disease, HPB surgery outcomes
- "endoscopy": endoscopic procedures and techniques — colonoscopy, upper GI endoscopy,
  EUS, ERCP, endoscopic therapy, capsule endoscopy, advanced endoscopy, adenoma detection,
  polyp management, endoscopic innovations
- "guideline": official clinical practice guidelines or consensus documents from BSG, NICE,
  EASL, AASLD, AGA, ACG, ESGE, ECCO, UEG, ACPGBI, ASGE — NOT a research paper
- "exclude": set this if ANY of the following apply:
    * Primarily molecular biology, cell signalling, mouse/animal models, or in-vitro studies
      with no direct human clinical application
    * Genomics, proteomics, metabolomics, or biomarker discovery studies without clinical outcomes
    * Mechanistic or pathophysiology studies not reporting patient outcomes
    * Paediatric-only studies
    * Unrelated specialty (cardiology, neurology, oncology outside GI, etc.)
    * Basic science with no clear near-term clinical relevance
  Be strict — if a paper is primarily laboratory/molecular even if it mentions patients, exclude it.
  Prefer real-world clinical studies: RCTs, cohort studies, registries, systematic reviews,
  meta-analyses, and clinical trials reporting patient outcomes.

subcategory: short label e.g. "MASLD", "IBD", "Pancreatic Cancer", "Colonoscopy", "HCC", "PSC"

headline: one punchy sentence (max 20 words) summarising the main finding for a clinician.

key_findings: 2-3 sentences. What was found? Include numbers and effect sizes where available.

clinical_relevance: 1-2 sentences on why this matters for NHS clinical practice.

study_type: "RCT", "Meta-analysis", "Cohort study", "Case-control", "Registry study",
"Systematic review", "Clinical trial", "Clinical Guideline", "Molecular study", etc.

quality_flag:
- "high": large RCT, meta-analysis of RCTs, large well-powered cohort, landmark trial
- "moderate": smaller RCT, observational, registry, systematic review without meta-analysis
- "preliminary": pilot, small case series, animal/mechanistic study, biomarker discovery

practice_changing: true ONLY if ALL FIVE criteria are met:
  1. quality_flag is "high"
  2. Published in NEJM, Lancet, Nature Medicine, BMJ, Gastroenterology, Gut,
     Journal of Hepatology, or Lancet Gastroenterology & Hepatology
  3. The finding directly overturns or substantially changes current standard of care
  4. Benefit to patients is large, clinically meaningful, and statistically robust
  5. A UK NHS consultant gastroenterologist would change clinical practice based on this result alone
  Be extremely strict. Expect 0-1 papers per digest. Incremental advances, confirmatory studies,
  subgroup analyses, and mechanistic insights do NOT qualify. If in doubt, set false.

practice_changing_reason: If true, 2-3 sentences: what was the previous standard of care,
what has changed, and what a clinician should now do differently.
If false, set to ""."""


class PaperSummary(BaseModel):
    """Schema the model must answer in. Structured outputs enforce it, so the
    reply always parses."""
    category: Literal["hepatology", "luminal", "hpb", "endoscopy", "exclude", "guideline"]
    subcategory: str
    headline: str
    key_findings: str
    clinical_relevance: str
    study_type: str
    quality_flag: Literal["high", "moderate", "preliminary"]
    practice_changing: bool
    practice_changing_reason: str


def summarise_paper(paper: dict, client: anthropic.Anthropic) -> Optional[dict]:
    """Call Claude Sonnet to categorise and summarise a paper.

    Returns the paper with the summary fields added, or None if the paper
    could not be summarised (refusal, truncated reply). API errors such as a
    bad key or no credit are raised so the caller can stop the run.
    """
    response = client.beta.messages.parse(
        model=ANTHROPIC_MODEL,
        # Thinking is on by default on this model and counts toward
        # max_tokens, so leave room for it as well as the JSON reply.
        max_tokens=4000,
        output_config={"effort": "low"},
        output_format=PaperSummary,
        # If a safety classifier declines a paper, retry it on Anthropic's
        # recommended fallback model instead of losing the paper.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Title: {paper['title']}\n\nAbstract: {paper['abstract']}"}],
    )

    if response.stop_reason == "refusal":
        print("  ✗ Skipped: the model declined to summarise this paper")
        return None
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        print(f"  ✗ Skipped: incomplete reply (stop_reason={response.stop_reason})")
        return None

    paper.update(response.parsed_output.model_dump())
    return paper


# ── Main orchestrator ──────────────────────────────────────────────────────────

def run_digest(api_key: str, days_back: int = 7) -> dict:
    # The SDK retries rate limits (429), overloads (529) and other transient
    # errors with backoff on its own.
    client = anthropic.Anthropic(api_key=api_key, max_retries=5)

    print(f"🔍 Searching PubMed for past {days_back} days across {len(JOURNALS)} journals...")
    pmids = search_pubmed(build_query(days_back))
    print(f"   Found {len(pmids)} articles")

    if not pmids:
        return {"hepatology": [], "luminal": [], "hpb": [], "endoscopy": [],
                "guidelines": [], "metadata": {"total": 0}}

    print("📥 Fetching abstracts...")
    articles = fetch_abstracts(pmids)  # already sorted by journal priority
    print(f"   {len(articles)} articles with usable abstracts (sorted by journal priority)")

    print("🤖 Summarising with Claude Sonnet 5.5...")
    hepatology, luminal, hpb, endoscopy, guidelines = [], [], [], [], []
    excluded = 0
    summarised = 0
    failed = 0

    for i, paper in enumerate(articles):
        # Stop early once all sections are full
        if (len(hepatology) >= LIMITS["hepatology"] and
            len(hpb)        >= LIMITS["hpb"] and
            len(luminal)    >= LIMITS["luminal"] and
            len(endoscopy)  >= LIMITS["endoscopy"]):
            print(f"   All sections full after {i+1} papers — stopping early")
            break

        print(f"   [{i+1}/{len(articles)}] {paper['title'][:70]}...")
        try:
            result = summarise_paper(paper, client)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError,
                anthropic.NotFoundError, anthropic.BadRequestError):
            # Bad key, no access to the model, no credit or a malformed
            # request: every later paper would fail the same way, so stop now
            # rather than emailing an empty digest.
            raise
        except anthropic.APIError as e:
            print(f"  ✗ Failed: {e}")
            result = None
        if result is None:
            failed += 1
            if summarised == 0 and failed >= 5:
                raise RuntimeError("The first 5 papers all failed to summarise - stopping. "
                                   "Check the Anthropic API status and the errors above.")
            continue
        summarised += 1

        cat = result.get("category", "exclude")

        if cat == "exclude":
            excluded += 1
        elif cat == "hepatology" and len(hepatology) < LIMITS["hepatology"]:
            hepatology.append(result)
        elif cat == "hpb" and len(hpb) < LIMITS["hpb"]:
            hpb.append(result)
        elif cat == "luminal" and len(luminal) < LIMITS["luminal"]:
            luminal.append(result)
        elif cat == "endoscopy" and len(endoscopy) < LIMITS["endoscopy"]:
            endoscopy.append(result)
        elif cat == "guideline":
            guidelines.append(result)
        # If a section is full, the paper is skipped (already have better ones from priority sort)

    # Sort each section: practice-changing first, then high quality
    quality_order = {"high": 0, "moderate": 1, "preliminary": 2}
    for lst in [hepatology, luminal, hpb, endoscopy]:
        lst.sort(key=lambda x: (
            0 if x.get("practice_changing") else 1,
            quality_order.get(x.get("quality_flag", "moderate"), 1),
        ))

    total = len(hepatology) + len(luminal) + len(hpb) + len(endoscopy)
    print(f"\n✅ Done. Hepatology: {len(hepatology)} | HPB: {len(hpb)} | "
          f"Luminal: {len(luminal)} | Endoscopy: {len(endoscopy)} | "
          f"Guidelines: {len(guidelines)} | Excluded: {excluded}")
    print(f"   Total papers in digest: {total}/20")

    return {
        "hepatology": hepatology,
        "luminal":    luminal,
        "hpb":        hpb,
        "endoscopy":  endoscopy,
        "guidelines": guidelines,
        "metadata": {
            "total_fetched":  len(articles),
            "excluded":       excluded,
            "failed":         failed,
            "generated_at":   datetime.now().isoformat(),
            "period_days":    days_back,
        }
    }
