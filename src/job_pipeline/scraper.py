import re
import time
from datetime import datetime, date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.job_pipeline.db import Session, JobPosting

BASE = "https://www.myjobmag.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; da-job-pipeline/1.0)"}

SKILL_KEYWORDS = {
    "has_sql":     ["sql", "mysql", "postgresql", "postgres"],
    "has_python":  ["python", "pandas", "numpy"],
    "has_tableau": ["tableau"],
    "has_powerbi": ["power bi", "powerbi"],
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


def scrape_jobs(keyword: str = "data analyst", location: str = "lagos", pages: int = 1) -> list[dict]:
    """Orchestrate: listing pages → detail pages → merged records."""
    all_jobs = []
    for page in range(1, pages + 1):
        url = f"{BASE}/search/jobs?q={keyword.replace(' ', '+')}&location={location}&page={page}"
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
            all_jobs.append({**card, **detail, **skills})
            time.sleep(0.5)  # polite crawling
    return all_jobs


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
    print("=== Scraping 1 page and saving to DB ===")
    jobs = scrape_jobs(keyword="data analyst", location="lagos", pages=1)
    print(f"Parsed: {len(jobs)}")
    inserted, skipped = save_jobs(jobs)
    print(f"Inserted: {inserted}  |  Skipped (already in DB): {skipped}")
