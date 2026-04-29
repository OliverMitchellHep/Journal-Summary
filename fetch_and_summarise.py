"""
fetch_and_summarise.py
Fetches last 7 days of papers from PubMed across target GI/hepatology journals,
summarises each with Claude Haiku, and returns structured data ready for PDF generation.

Paper limits: 10 hepatology+HPB, 5 luminal GI, 5 endoscopy = 20 total
Focus: clinical studies (RCTs, cohorts, meta-analyses). Molecular/basic science excluded.
"""

import time
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

# ── Journal list ───────────────────────────────────────────────────────────────
JOURNALS = [
    "Gut", "Front Gastroenterol", "BMJ Open Gastroenterol",
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
    "Front Gastroenterol": 3, "BMJ Open Gastroenterol": 3, "Liver Int": 3,
    "United European Gastroenterol J": 3, "Colorectal Dis": 3, "Endosc Int Open": 3,
}

UK_JOURNALS = {
    "Gut", "Front Gastroenterol", "BMJ Open Gastroenterol", "Lancet",
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
ANTHROPIC_API   = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


# ── PubMed helpers ─────────────────────────────────────────────────────────────

def build_query(days_back: int = 7) -> str:
    end   = datetime.today()
    start = end - timedelta(days=days_back)
    date_range     = f"{start.strftime('%Y/%m/%d')}:{end.strftime('%Y/%m/%d')}[dp]"
    journal_clause = " OR ".join([f'"{j}"[ta]' for j in JOURNALS])
    return f"({journal_clause}) AND {date_range}"


def search_pubmed(query: str, max_results: int = 200) -> list[str]:
    params = {
        "db": "pubmed", "term": query, "retmax": max_results,
        "retmode": "json", "usehistory": "y",
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

            pub_date     = medline.find(".//PubDate")
            pub_date_str = f"{pub_date.findtext('Month', '')} {pub_date.findtext('Year', '')}".strip()

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

            # Journal priority scoring
            priority = 3
            is_uk    = False
            for j, p in JOURNAL_PRIORITY.items():
                if j.lower() in journal_full.lower() or j.lower() in journal_abbr.lower():
                    priority = p
                    break
            for j in UK_JOURNALS:
                if j.lower() in journal_full.lower() or j.lower() in journal_abbr.lower():
                    is_uk = True
                    break

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
        return {"hepatology": [], "luminal": [], "hpb": [], "endoscopy": [],
                "guidelines": [], "metadata": {"total": 0}}

    print("📥 Fetching abstracts...")
    articles = fetch_abstracts(pmids)  # already sorted by journal priority
    print(f"   {len(articles)} articles with usable abstracts (sorted by journal priority)")

    print("🤖 Summarising with Claude Haiku...")
    hepatology, luminal, hpb, endoscopy, guidelines = [], [], [], [], []
    excluded = 0

    for i, paper in enumerate(articles):
        # Stop early once all sections are full
        if (len(hepatology) >= LIMITS["hepatology"] and
            len(hpb)        >= LIMITS["hpb"] and
            len(luminal)    >= LIMITS["luminal"] and
            len(endoscopy)  >= LIMITS["endoscopy"]):
            print(f"   All sections full after {i+1} papers — stopping early")
            break

        print(f"   [{i+1}/{len(articles)}] {paper['title'][:70]}...")
        result = summarise_paper(paper, api_key)
        time.sleep(0.3)
        if result is None:
            continue

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
            "generated_at":   datetime.now().isoformat(),
            "period_days":    days_back,
        }
    }
