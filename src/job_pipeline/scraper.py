import re
import time
from datetime import datetime, date, timezone
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from src.job_pipeline.db import Session, JobPosting

BASE = "https://www.myjobmag.com"
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; da-job-pipeline/1.0)"}
INTERNATIONAL_CATEGORY = "International / Remote"
INTERNATIONAL_TERMS = (
    "software", "developer", "engineer", "data", "machine learning", "devops",
    "security", "quality assurance", "qa ", "cloud", "analyst", "scientist",
)

SKILL_KEYWORDS = {
    "has_sql":     ["sql", "mysql", "postgresql", "postgres"],
    "has_python":  ["python", "pandas", "numpy"],
    "has_tableau": ["tableau"],
    "has_powerbi": ["power bi", "powerbi"],
}

STEM_CATEGORIES = {
    "Data & AI": ["data analyst", "data scientist", "machine learning"],
    "Software": ["software engineer", "software developer", "frontend developer", "backend developer"],
    "Cybersecurity": ["cybersecurity", "security analyst", "information security"],
    "Cloud & DevOps": ["devops", "cloud engineer", "site reliability engineer"],
    "QA & Testing": ["qa engineer", "quality assurance", "test engineer"],
    "Engineering": ["electrical engineer", "mechanical engineer", "civil engineer", "biomedical engineer"],
}

LOCATION_RE = re.compile(r"\bin\s+([A-Z][a-zA-Z]+(?:,\s*[A-Z][a-zA-Z]+)?)", re.IGNORECASE)


def fetch(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.text
    except requests.RequestException as e:
        print(f"  [fetch error] {url}: {e}")
    return None


def fetch_json(url: str) -> dict | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code == 200:
            return response.json()
    except (requests.RequestException, ValueError) as error:
        print(f"  [json fetch error] {url}: {error}")
    return None


def parse_listing(html: str) -> list[dict]:
    """Return [{title, company, url}, ...] from a search results page."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.select("li.mag-b h2 a"):
        href = card.get("href", "")
        text = card.get_text(" ", strip=True)
        # "Data Analyst at Ascentech Services Limited"
        if " at " in text:
            title, company = text.rsplit(" at ", 1)
        else:
            title, company = text, ""
        jobs.append({
            "title": title.strip(),
            "company": company.strip(),
            "url": urljoin(BASE, href),
        })
    return jobs


def parse_detail(html: str) -> dict:
    """Extract description, location, posted date from a detail page."""
    soup = BeautifulSoup(html, "html.parser")

    desc_el = soup.select_one("div.job-details")
    description = desc_el.get_text(" ", strip=True) if desc_el else ""

    date_el = soup.select_one("#posted-date")
    posted = date.today()
    if date_el:
        raw = date_el.get_text(" ", strip=True).replace("Posted:", "").strip()
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                posted = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                continue

    # Location from meta description: "...for Data Analyst in Lagos, Nigeria..."
    meta = soup.find("meta", attrs={"name": "description"})
    location = "Nigeria"
    if meta and meta.get("content"):
        m = LOCATION_RE.search(meta["content"])
        if m:
            location = m.group(1).strip()

    return {"description": description, "date_posted": posted, "location": location}


def detect_skills(text: str) -> dict:
    low = text.lower()
    return {k: any(kw in low for kw in v) for k, v in SKILL_KEYWORDS.items()}


def scrape_jobs(
    keyword: str = "data analyst",
    location: str = "lagos",
    pages: int = 1,
    category: str = "Data & AI",
) -> list[dict]:
    """Orchestrate: listing pages → detail pages → merged records."""
    all_jobs = []
    for page in range(1, pages + 1):
        url = f"{BASE}/search/jobs?q={quote_plus(keyword)}&location={quote_plus(location)}&page={page}"
        print(f"[listing] page {page}: {url}")
        html = fetch(url)
        if not html:
            break
        cards = parse_listing(html)
        print(f"  found {len(cards)} cards")
        if not cards:
            break

        for i, card in enumerate(cards, 1):
            print(f"  [{i}/{len(cards)}] {card['title'][:60]}")
            detail_html = fetch(card["url"])
            if not detail_html:
                continue
            detail = parse_detail(detail_html)
            skills = detect_skills(detail["description"])
            all_jobs.append({**card, **detail, **skills, "category": category})
            time.sleep(0.5)  # polite crawling
    return all_jobs


def scrape_stem_jobs(location: str = "lagos", pages: int = 1, categories: list[str] | None = None) -> list[dict]:
    """Search local STEM families plus international remote STEM roles."""
    selected = categories or list(STEM_CATEGORIES)
    all_jobs = []
    seen_urls = set()
    for category in selected:
        for keyword in STEM_CATEGORIES.get(category, []):
            for job in scrape_jobs(keyword, location, pages, category):
                if job["url"] not in seen_urls:
                    seen_urls.add(job["url"])
                    all_jobs.append(job)
    if categories is None:
        for job in scrape_international_jobs():
            if job["url"] not in seen_urls:
                seen_urls.add(job["url"])
                all_jobs.append(job)
    return all_jobs


def scrape_international_jobs() -> list[dict]:
    """Fetch remote STEM jobs from Arbeitnow's public international feed."""
    payload = fetch_json(ARBEITNOW_API) or {}
    jobs = []
    for item in payload.get("data", []):
        title = item.get("title", "").strip()
        description = BeautifulSoup(item.get("description", ""), "html.parser").get_text(" ", strip=True)
        haystack = f"{title} {description}".lower()
        if not item.get("remote") or not any(term in haystack for term in INTERNATIONAL_TERMS):
            continue
        created_at = item.get("created_at")
        posted = date.today()
        if isinstance(created_at, (int, float)):
            posted = datetime.fromtimestamp(created_at, tz=timezone.utc).date()
        skills = detect_skills(description)
        jobs.append({
            "title": title,
            "company": item.get("company_name", "").strip(),
            "url": item.get("url", ""),
            "description": description,
            "location": item.get("location") or "Remote / International",
            "date_posted": posted,
            "category": INTERNATIONAL_CATEGORY,
            **skills,
        })
    print(f"[international] found {len(jobs)} remote STEM roles")
    return jobs


def save_jobs(jobs: list[dict]) -> tuple[int, int]:
    """Insert new jobs (dedupe by URL). Returns (inserted, skipped)."""
    session = Session()
    inserted, skipped = 0, 0
    try:
        for j in jobs:
            if session.query(JobPosting).filter_by(url=j["url"]).first():
                skipped += 1
                continue
            session.add(JobPosting(
                title=j["title"][:255],
                company=j["company"][:255],
                location=j["location"][:255],
                date_posted=j["date_posted"],
                url=j["url"][:500],
                category=j.get("category", "Data & AI")[:80],
                description=j["description"],
                has_sql=j["has_sql"],
                has_python=j["has_python"],
                has_tableau=j["has_tableau"],
                has_powerbi=j["has_powerbi"],
            ))
            inserted += 1
        session.commit()
    finally:
        session.close()
    return inserted, skipped


if __name__ == "__main__":
    print("=== Scraping STEM jobs and saving to DB ===")
    jobs = scrape_stem_jobs(location="lagos", pages=1)
    print(f"Parsed: {len(jobs)}")
    inserted, skipped = save_jobs(jobs)
    print(f"Inserted: {inserted}  |  Skipped (already in DB): {skipped}")
