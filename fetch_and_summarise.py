"""
fetch_and_summarise.py
Fetches last 7 days of papers from PubMed across target GI/hepatology journals,
summarises each with Claude Haiku, and returns structured data ready for PDF generation.
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

# ── Journal priority tiers for ranking (lower = higher priority) ───────────────
# Tier 1: Highest impact general + specialist GI/hepatology
# Tier 2: Strong specialist journals
# Tier 3: Good but lower impact
JOURNAL_PRIORITY = {
    # Tier 1 — highest impact
    "N Engl J Med":                  1,
    "Lancet":                        1,
    "Nat Med":                       1,
    "BMJ":                           1,
    "Gastroenterology":              1,
    "Gut":                           1,
    "J Hepatol":                     1,
    "Lancet Gastroenterol Hepatol":  1,
    # Tier 2 — strong specialist
    "Am J Gastroenterol":            2,
    "Hepatology":                    2,
    "JHEP Rep":                      2,
    "Clin Gastroenterol Hepatol":    2,
    "Endoscopy":                     2,
    "Aliment Pharmacol Ther":        2,
    # Tier 3 — good but lower impact
    "Front Gastroenterol":           3,
    "BMJ Open Gastroenterol":        3,
    "Liver Int":                     3,
    "United European Gastroenterol J": 3,
    "Colorectal Dis":                3,
    "Endosc Int Open":               3,
}

# UK-based journals get a boost in priority
UK_JOURNALS = {
    "Gut", "Front Gastroenterol", "BMJ Open Gastroenterol",
    "Lancet", "Lancet Gastroenterol Hepatol", "BMJ",
    "Aliment Pharmacol Ther", "Colorectal Dis",
}

MAX_PAPERS = 20  # Maximum papers to include in the digest

PUBMED_BASE     = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ANTHROPIC_API   = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

# ── PubMed helpers ─────────────────────────────────────────────────────────────

def build_query(days_back: int = 7) -> str:
    end = datetime.today()
    start = end - timedelta(days=days_back)
    date_range = f"{start.strftime('%Y/%m/%d')}:{end.strftime('%Y/%m/%d')}[dp]"
    journal_clause = " OR ".join([f'"{j}"[ta]' for j in JOURNALS])
    return f"({journal_clause}) AND {date_range}"


def search_pubmed(query: str, max_results: int = 200) -> list[str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "usehistory": "y",
    }
    r = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    return r.json()["esearchresult"]["idlist"]


def fetch_abstracts(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract"}
    r = requests.get(f"{PUBMED_BASE}/efetch.fcgi", params=params, timeout=60)
    r.raise_for_status()
    return parse_pubmed_xml(r.text)


def parse_pubmed_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    articles = []
    for article in root.findall(".//PubmedArticle"):
        try:
            medline = article.find("MedlineCitation")
            art = medline.find("Article")

            title_el = art.find("ArticleTitle")
            title = "".join(title_el.itertext()) if title_el is not None else "No title"

            abstract_texts = art.findall(".//AbstractText")
            abstract = " ".join("".join(a.itertext()) for a in abstract_texts) if abstract_texts else ""

            journal_el = art.find(".//Journal/ISOAbbreviation")
            journal_abbr = journal_el.text if journal_el is not None else ""
            journal_full_el = art.find(".//Journal/Title")
            journal_full = journal_full_el.text if journal_full_el is not None else journal_abbr

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

            pub_date = medline.find(".//PubDate")
            pub_date_str = f"{pub_date.findtext('Month', '')} {pub_date.findtext('Year', '')}".strip()

            pmid_el = medline.find("PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            doi = ""
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text
                    break

            pub_types = [pt.text for pt in art.findall(".//PublicationType")]
            skip_types = {"Letter", "Editorial", "Retraction of Publication",
                          "Published Erratum", "Comment", "News"}
            if any(pt in skip_types for pt in pub_types):
                continue

            if len(abstract) < 100:
                continue

            # Compute journal priority score (lower = better)
            # Match against our priority dict using partial matching
            priority = 3  # default tier 3
            is_uk = False
            for j, p in JOURNAL_PRIORITY.items():
                if j.lower() in (journal_abbr or "").lower() or j.lower() in journal_full.lower():
                    priority = p
                    break
            for j in UK_JOURNALS:
                if j.lower() in (journal_abbr or "").lower() or j.lower() in journal_full.lower():
                    is_uk = True
                    break

            articles.append({
                "pmid": pmid,
                "title": title,
                "authors": author_str,
                "journal": journal_full,
                "journal_abbr": journal_abbr,
                "pub_date": pub_date_str,
                "abstract": abstract[:3000],
                "doi": doi,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "_priority": priority,
                "_is_uk": is_uk,
            })
        except Exception:
            continue

    # Sort by priority tier, UK journals boosted, then return top candidates
    # UK journals in tier N are treated as tier N-0.5
    articles.sort(key=lambda x: (x["_priority"] - (0.5 if x["_is_uk"] else 0)))
    return articles


# ── Claude Haiku summarisation ─────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a specialist medical AI assistant helping a UK NHS consultant gastroenterologist 
stay up to date with research. You will be given a paper title and abstract.

Return ONLY valid JSON (no markdown fences, no preamble) with this exact schema:
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

category rules — assign ONE category only:
- "hepatology": liver parenchymal disease — NAFLD/MASLD, MASH, cirrhosis, portal hypertension, viral hepatitis (HBV/HCV/HDV/HEV), alcohol-related liver disease, autoimmune hepatitis, PBC, PSC, liver transplantation, HCC
- "luminal": luminal gastrointestinal disease — IBD (Crohn's, UC), colorectal cancer, IBS, coeliac disease, motility disorders, upper GI (oesophagus, stomach, small bowel), gut microbiome
- "hpb": hepatopancreatobiliary surgery and pancreatic disease — pancreatic cancer, pancreatitis, pancreatic cysts, biliary tract cancer, cholangiocarcinoma, gallbladder disease, HPB surgery outcomes
- "endoscopy": endoscopic procedures and techniques — colonoscopy, upper GI endoscopy, EUS, ERCP, endoscopic therapy, capsule endoscopy, advanced endoscopy, adenoma detection, polyp management
- "guideline": official clinical practice guidelines, position statements or consensus documents from BSG, NICE, EASL, AASLD, AGA, ACG, ESGE, ECCO, UEG, ACPGBI, ASGE — NOT a research paper
- "exclude": not relevant to GI/hepatology, basic science only with no clinical application, paediatric-only, or irrelevant specialty

subcategory: short label e.g. "MASLD", "IBD", "Pancreatic Cancer", "Colonoscopy", "HCC", "PSC" etc.

headline: one punchy sentence (max 20 words) summarising the main finding for a clinician.

key_findings: 2-3 sentences covering what was found, with numbers and effect sizes where available.

clinical_relevance: 1-2 sentences on why this matters for NHS clinical practice.

study_type: e.g. "RCT", "Meta-analysis", "Cohort study", "Case-control", "Review", "Clinical Guideline"

quality_flag:
- "high": large RCT, meta-analysis of RCTs, large well-powered cohort, landmark trial
- "moderate": smaller RCT, observational study, registry data, systematic review without meta-analysis
- "preliminary": pilot study, small case series, animal/mechanistic study with limited human data

practice_changing: true ONLY if ALL FIVE criteria are met:
  1. quality_flag is "high"
  2. Published in a tier-1 journal (NEJM, Lancet, Nature Medicine, BMJ, Gastroenterology, Gut, Journal of Hepatology, Lancet Gastroenterology & Hepatology)
  3. The finding directly overturns or substantially changes current standard of care
  4. The benefit to patients is large, clinically meaningful, and statistically robust
  5. A UK NHS consultant gastroenterologist would change their clinical practice based on this result alone
  
  Be extremely strict. Expect no more than 1-2 papers per digest to qualify. Incremental advances,
  confirmatory studies, subgroup analyses, and mechanistic insights do NOT qualify regardless of journal.
  If in doubt, set to false.

practice_changing_reason: If true, write 2-3 sentences: what was the previous standard of care,
what specifically has changed, and what a clinician should now do differently in practice.
If false, set to ""."""


def summarise_paper(paper: dict, api_key: str) -> Optional[dict]:
    """Call Claude Haiku to categorise and summarise a paper."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 700,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": f"Title: {paper['title']}\n\nAbstract: {paper['abstract']}"}],
    }

    for attempt in range(3):
        try:
            r = requests.post(ANTHROPIC_API, headers=headers, json=body, timeout=30)
            r.raise_for_status()
            raw = r.json()["content"][0]["text"].strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            summary = json.loads(raw)
            paper.update(summary)
            return paper
        except Exception as e:
            if attempt == 2:
                print(f"  ✗ Failed: {e}")
                return None
            time.sleep(2 ** attempt)
    return None


# ── Main orchestrator ──────────────────────────────────────────────────────────

def run_digest(api_key: str, days_back: int = 7) -> dict:
    print(f"🔍 Searching PubMed for past {days_back} days across {len(JOURNALS)} journals...")
    pmids = search_pubmed(build_query(days_back))
    print(f"   Found {len(pmids)} articles")

    if not pmids:
        return {"hepatology": [], "luminal": [], "hpb": [], "endoscopy": [], "guidelines": [], "metadata": {"total": 0}}

    print("📥 Fetching abstracts...")
    articles = fetch_abstracts(pmids)  # already sorted by journal priority
    print(f"   {len(articles)} articles with usable abstracts (sorted by journal priority)")

    print("🤖 Summarising with Claude Haiku...")
    hepatology, luminal, hpb, endoscopy, guidelines = [], [], [], [], []
    excluded = 0
    total_included = 0

    for i, paper in enumerate(articles):
        # Stop sending to AI once we have enough included papers
        # We process up to 3x the limit to ensure we fill all categories
        if total_included >= MAX_PAPERS and i > MAX_PAPERS * 3:
            print(f"   Reached processing limit, stopping early")
            break

        print(f"   [{i+1}/{len(articles)}] {paper['title'][:70]}...")
        result = summarise_paper(paper, api_key)
        time.sleep(0.3)
        if result is None:
            continue

        cat = result.get("category", "exclude")
        if cat == "exclude":
            excluded += 1
        elif cat == "hepatology":
            hepatology.append(result)
            total_included += 1
        elif cat == "luminal":
            luminal.append(result)
            total_included += 1
        elif cat == "hpb":
            hpb.append(result)
            total_included += 1
        elif cat == "endoscopy":
            endoscopy.append(result)
            total_included += 1
        elif cat == "guideline":
            guidelines.append(result)

    # Sort each section: practice-changing first, then high quality
    quality_order = {"high": 0, "moderate": 1, "preliminary": 2}
    for lst in [hepatology, luminal, hpb, endoscopy]:
        lst.sort(key=lambda x: (
            0 if x.get("practice_changing") else 1,
            quality_order.get(x.get("quality_flag", "moderate"), 1),
        ))

    # Trim each section proportionally if over limit
    # Distribute MAX_PAPERS across sections, ensuring no section is empty if it has papers
    all_sections = [
        ("hepatology", hepatology),
        ("luminal", luminal),
        ("hpb", hpb),
        ("endoscopy", endoscopy),
    ]
    non_empty = [(name, lst) for name, lst in all_sections if lst]
    if total_included > MAX_PAPERS and non_empty:
        per_section = max(2, MAX_PAPERS // len(non_empty))
        for name, lst in non_empty:
            del lst[per_section:]

    print(f"\n✅ Done. Hepatology: {len(hepatology)} | Luminal: {len(luminal)} | HPB: {len(hpb)} | Endoscopy: {len(endoscopy)} | Guidelines: {len(guidelines)} | Excluded: {excluded}")

    return {
        "hepatology": hepatology,
        "luminal": luminal,
        "hpb": hpb,
        "endoscopy": endoscopy,
        "guidelines": guidelines,
        "metadata": {
            "total_fetched": len(articles),
            "excluded": excluded,
            "generated_at": datetime.now().isoformat(),
            "period_days": days_back,
        }
    }
