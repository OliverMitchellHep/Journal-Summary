"""
fetch_and_summarise.py
Fetches last 7 days of papers from PubMed across target GI/hepatology journals,
summarises each with Google Gemini Flash (free tier), and returns structured data
ready for PDF generation.
"""

import os
import time
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

# ── Journal list (PubMed journal title abbreviations) ─────────────────────────
JOURNALS = [
    "Gut",
    "Front Gastroenterol",
    "BMJ Open Gastroenterol",
    "Gastroenterology",
    "Am J Gastroenterol",
    "Clin Gastroenterol Hepatol",
    "N Engl J Med",
    "Lancet",
    "Lancet Gastroenterol Hepatol",
    "BMJ",
    "Nat Med",
    "J Hepatol",
    "JHEP Rep",
    "Hepatology",
    "Liver Int",
    "Aliment Pharmacol Ther",
    "United European Gastroenterol J",
    "Colorectal Dis",
    "Endoscopy",
    "Endosc Int Open",
]

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# ── PubMed helpers ─────────────────────────────────────────────────────────────

def build_query(days_back: int = 7) -> str:
    end = datetime.today()
    start = end - timedelta(days=days_back)
    date_range = f"{start.strftime('%Y/%m/%d')}:{end.strftime('%Y/%m/%d')}[dp]"
    journal_clause = " OR ".join([f'"{j}"[ta]' for j in JOURNALS])
    return f"({journal_clause}) AND {date_range}"


def search_pubmed(query: str, max_results: int = 200) -> list[str]:
    """Return list of PMIDs matching query."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "usehistory": "y",
    }
    r = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["esearchresult"]["idlist"]


def fetch_abstracts(pmids: list[str]) -> list[dict]:
    """Fetch full records for a list of PMIDs."""
    if not pmids:
        return []
    ids = ",".join(pmids)
    params = {"db": "pubmed", "id": ids, "retmode": "xml", "rettype": "abstract"}
    r = requests.get(f"{PUBMED_BASE}/efetch.fcgi", params=params, timeout=60)
    r.raise_for_status()
    return parse_pubmed_xml(r.text)


def parse_pubmed_xml(xml_text: str) -> list[dict]:
    """Parse PubMed XML into list of article dicts."""
    root = ET.fromstring(xml_text)
    articles = []
    for article in root.findall(".//PubmedArticle"):
        try:
            medline = article.find("MedlineCitation")
            art = medline.find("Article")

            # Title
            title_el = art.find("ArticleTitle")
            title = "".join(title_el.itertext()) if title_el is not None else "No title"

            # Abstract
            abstract_texts = art.findall(".//AbstractText")
            abstract = " ".join("".join(a.itertext()) for a in abstract_texts) if abstract_texts else ""

            # Journal
            journal_el = art.find(".//Journal/Title")
            journal = journal_el.text if journal_el is not None else "Unknown journal"

            # Authors
            authors = []
            for author in art.findall(".//Author"):
                ln = author.find("LastName")
                fn = author.find("ForeName")
                if ln is not None:
                    name = ln.text
                    if fn is not None:
                        name += f" {fn.text[0]}"
                    authors.append(name)
            author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")

            # Publication date
            pub_date = medline.find(".//PubDate")
            year = pub_date.findtext("Year", "")
            month = pub_date.findtext("Month", "")
            pub_date_str = f"{month} {year}".strip()

            # PMID
            pmid_el = medline.find("PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            # DOI
            doi = ""
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text
                    break

            # Article type filter — skip letters, corrections, errata
            pub_types = [pt.text for pt in art.findall(".//PublicationType")]
            skip_types = {"Letter", "Editorial", "Retraction of Publication",
                          "Published Erratum", "Comment", "News"}
            if any(pt in skip_types for pt in pub_types):
                continue

            # Must have an abstract to be useful
            if len(abstract) < 100:
                continue

            articles.append({
                "pmid": pmid,
                "title": title,
                "authors": author_str,
                "journal": journal,
                "pub_date": pub_date_str,
                "abstract": abstract[:3000],  # cap to avoid token bloat
                "doi": doi,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        except Exception:
            continue
    return articles


# ── Gemini summarisation ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a specialist medical AI assistant helping a UK NHS gastroenterologist 
stay up to date with research. You will be given a paper title and abstract. 

Return ONLY valid JSON (no markdown fences, no preamble) with this exact schema:
{
  "category": "hepatology" | "luminal_gi" | "both" | "exclude" | "guideline",
  "subcategory": string,
  "headline": string,
  "key_findings": string,
  "clinical_relevance": string,
  "study_type": string,
  "quality_flag": "high" | "moderate" | "preliminary",
  "practice_changing": true | false,
  "practice_changing_reason": string
}

category rules:
- "hepatology": liver disease, NAFLD/MASLD, cirrhosis, viral hepatitis, cholestatic disease, liver cancer, transplant
- "luminal_gi": IBD, colorectal cancer, endoscopy, motility, upper GI, coeliac, IBS, polyps, CRC screening
- "both": clearly covers both domains equally
- "exclude": basic science only with no clinical translation, or irrelevant to adult GI/hepatology
- "guideline": official clinical practice guidelines, position statements, or consensus documents from recognised societies
  (e.g. BSG, NICE, EASL, AASLD, AGA, ACG, ESGE, ECCO, UEG, ACPGBI, ASGE). NOT a research paper with recommendations.

subcategory: a short label e.g. "IBD", "MASLD", "CRC Screening", "Endoscopy", "HCC", "Viral Hepatitis" etc.

headline: one punchy sentence (max 20 words) summarising the main finding for a clinician.

key_findings: 2-3 sentences. What did they find? Include numbers/effect sizes where available.

clinical_relevance: 1-2 sentences. Why does this matter for clinical practice in the NHS?

study_type: e.g. "RCT", "Meta-analysis", "Cohort study", "Case series", "Review", "Clinical Guideline"

quality_flag:
- "high": RCT, large well-designed cohort, meta-analysis of RCTs, landmark finding, major guideline
- "moderate": observational, registry, smaller RCT, systematic review without meta-analysis
- "preliminary": small study, pilot, animal/lab with limited human data

practice_changing: true ONLY if ALL of the following apply:
  1. quality_flag is "high"
  2. The finding directly contradicts current standard of care OR establishes a major new treatment/diagnostic standard
  3. It is likely to change what a consultant gastroenterologist does in clinic within the next 1-2 years
  Be STRICT — reserve this for genuinely landmark findings. Most papers should be false.

practice_changing_reason: If practice_changing is true, write 2-3 sentences explaining specifically WHY this changes 
practice: what was the previous standard, what has changed, and what clinicians should now do differently.
If practice_changing is false, set this to empty string ""."""


def summarise_paper(paper: dict, api_key: str) -> Optional[dict]:
    """Call Gemini Flash to categorise and summarise a paper. Returns enriched dict or None."""
    # Gemini takes system + user as a combined prompt
    full_prompt = f"""{SYSTEM_PROMPT}

Title: {paper['title']}

Abstract: {paper['abstract']}"""

    body = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,       # low temp for consistent structured output
            "maxOutputTokens": 700,
        },
    }

    url = f"{GEMINI_API}?key={api_key}"

    for attempt in range(3):
        try:
            r = requests.post(url, json=body, timeout=30)
            r.raise_for_status()
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Strip any accidental markdown fences
            raw = raw.replace("```json", "").replace("```", "").strip()
            summary = json.loads(raw)
            paper.update(summary)
            return paper
        except Exception as e:
            if attempt == 2:
                print(f"  ✗ Failed to summarise '{paper['title'][:60]}': {e}")
                return None
            wait = 15 if "429" in str(e) else 2 ** attempt
            time.sleep(wait)
    return None


# ── Main orchestrator ──────────────────────────────────────────────────────────

def run_digest(api_key: str, days_back: int = 7) -> dict:
    """
    Full pipeline: fetch → summarise → categorise.
    Returns dict with 'hepatology', 'luminal_gi', 'both' lists and metadata.
    """
    print(f"🔍 Searching PubMed for past {days_back} days across {len(JOURNALS)} journals...")
    query = build_query(days_back)
    pmids = search_pubmed(query)
    print(f"   Found {len(pmids)} articles")

    if not pmids:
        return {"hepatology": [], "luminal_gi": [], "metadata": {"total": 0}}

    print("📥 Fetching abstracts...")
    articles = fetch_abstracts(pmids)
    print(f"   {len(articles)} articles with usable abstracts")

    print("🤖 Summarising with Gemini...")
    hepatology = []
    luminal_gi = []
    guidelines = []
    excluded = 0

    for i, paper in enumerate(articles):
        print(f"   [{i+1}/{len(articles)}] {paper['title'][:70]}...")
        result = summarise_paper(paper, api_key)
        time.sleep(5)  # MUST be here — always pause whether success or failure
        if result is None:
            continue
        cat = result.get("category", "exclude")
        if cat == "exclude":
            excluded += 1
        elif cat == "hepatology":
            hepatology.append(result)
        elif cat == "luminal_gi":
            luminal_gi.append(result)
        elif cat == "both":
            hepatology.append(result)
            luminal_gi.append(result)
        elif cat == "guideline":
            guidelines.append(result)
            
    # Sort: practice-changing first, then high quality, then subcategory
    quality_order = {"high": 0, "moderate": 1, "preliminary": 2}
    for lst in [hepatology, luminal_gi]:
        lst.sort(key=lambda x: (
            0 if x.get("practice_changing") else 1,
            quality_order.get(x.get("quality_flag", "moderate"), 1),
            x.get("subcategory", "")
        ))

    print(f"\n✅ Done. Hepatology: {len(hepatology)} | Luminal GI: {len(luminal_gi)} | Guidelines: {len(guidelines)} | Excluded: {excluded}")

    return {
        "hepatology": hepatology,
        "luminal_gi": luminal_gi,
        "guidelines": guidelines,
        "metadata": {
            "total_fetched": len(articles),
            "excluded": excluded,
            "generated_at": datetime.now().isoformat(),
            "period_days": days_back,
        }
    }
