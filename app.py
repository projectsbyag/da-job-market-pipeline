from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from src.job_pipeline.db import JobPosting, Session, init_db
from src.job_pipeline.scraper import STEM_CATEGORIES, save_jobs, scrape_jobs, scrape_stem_jobs


STATIC_INDEX = Path(__file__).parent / "static" / "dashboard.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="STEM Job Market Pipeline", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def dashboard():
    if STATIC_INDEX.exists():
        return FileResponse(STATIC_INDEX)
    return {"service": "da-job-market-pipeline", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/categories")
def categories():
    return [{"name": name, "queries": queries} for name, queries in STEM_CATEGORIES.items()]


@app.get("/api/jobs")
def jobs(
    limit: int = Query(100, ge=1, le=500),
    category: str | None = Query(None),
    q: str | None = Query(None, min_length=1),
):
    session = Session()
    try:
        query = session.query(JobPosting)
        if category and category != "All STEM":
            query = query.filter(JobPosting.category == category)
        if q:
            pattern = f"%{q}%"
            query = query.filter(JobPosting.title.ilike(pattern) | JobPosting.company.ilike(pattern))
        records = query.order_by(JobPosting.date_posted.desc(), JobPosting.id.desc()).limit(limit).all()
        return [_serialize_job(record) for record in records]
    finally:
        session.close()


@app.post("/api/scrape")
def scrape(
    pages: int = Query(1, ge=1, le=10),
    keyword: str | None = Query(None),
    location: str = Query("lagos", min_length=1),
    category: str | None = Query(None),
):
    try:
        if keyword:
            parsed = scrape_jobs(keyword=keyword, location=location, pages=pages, category=category or "Data & AI")
        else:
            selected = [category] if category and category != "All STEM" else None
            parsed = scrape_stem_jobs(location=location, pages=pages, categories=selected)
        inserted, skipped = save_jobs(parsed)
        return {
            "parsed": len(parsed),
            "inserted": inserted,
            "skipped": skipped,
            "scope": category or "All STEM",
            "location": location,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Scrape failed") from exc


def _serialize_job(record: JobPosting) -> dict:
    return {
        "id": record.id,
        "title": record.title,
        "company": record.company,
        "location": record.location,
        "date_posted": record.date_posted.isoformat() if isinstance(record.date_posted, date) else None,
        "url": record.url,
        "category": record.category or "Data & AI",
        "description": record.description,
        "has_sql": record.has_sql,
        "has_python": record.has_python,
        "has_tableau": record.has_tableau,
        "has_powerbi": record.has_powerbi,
    }