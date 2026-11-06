# DA Job Market Pipeline

A small job-market data pipeline that collects Data Analyst postings from
[MyJobMag](https://www.myjobmag.com), extracts useful fields and skill flags,
and stores the results in SQLite or PostgreSQL.

## Features

- Scrapes job listings and detail pages for a keyword and location.
- Extracts title, company, location, description and posting date.
- Detects SQL, Python, Tableau and Power BI keywords.
- Deduplicates records by job URL.
- Provides a FastAPI service for querying jobs and triggering scrapes.
- Supports scheduled scraping through GitHub Actions and a Render deployment.

## Project layout

```text
.
├── app.py                         # FastAPI application
├── data/raw/                      # Sample HTML fixtures
├── requirements.txt
├── src/job_pipeline/db.py         # SQLAlchemy model and database setup
├── src/job_pipeline/scraper.py    # Fetching, parsing and persistence
└── .github/workflows/scrape.yml   # Daily Render trigger
```

## Requirements

- Python 3.11 or newer
- SQLite for local development, or PostgreSQL for production

## Local setup

```bash
git clone https://github.com/projectsbyag/da-job-market-pipeline.git
cd da-job-market-pipeline

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The application uses `sqlite:///data/jobs.db` when `DATABASE_URL` is not set.
To use another database, create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://user:password@host:5432/database
```

`.env` is ignored by Git. Never commit credentials or connection strings.

## Run locally

Start the API with Uvicorn:

```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/docs` for the interactive API documentation.
The database tables are created automatically when the application starts.

To run the scraper directly from the command line:

```bash
python -m src.job_pipeline.scraper
```

## API

### Health check

```http
GET /health
```

Returns a simple service status response.

### List jobs

```http
GET /api/jobs?limit=100
```

Returns the newest saved postings. `limit` accepts values from 1 to 500.

### Trigger a scrape

```bash
curl -X POST \
	"http://127.0.0.1:8000/api/scrape?pages=1&keyword=data%20analyst&location=lagos"
```

The response contains the number of records parsed, inserted and skipped as
duplicates. `pages` accepts values from 1 to 10.

### Dashboard

`GET /` serves `static/dashboard.html` when that file is present. Otherwise it
returns a basic service status response.

## Deployment

The Render service can use:

```text
Build command: pip install -r requirements.txt
Start command: uvicorn app:app --host 0.0.0.0 --port $PORT
```

Set `DATABASE_URL` in Render to the PostgreSQL connection string. The database
module accepts both `postgres://` and `postgresql://` prefixes.

The GitHub Actions workflow runs at 08:00 UTC every day and can also be run
manually. Add this repository secret:

```text
DASHBOARD_URL=https://your-render-service.onrender.com
```

The workflow sends `POST /api/scrape?pages=1` to the deployed service and
retries transient failures.

## Notes

- Scraping is polite but sequential: detail pages are requested with a short
	delay between requests.
- MyJobMag HTML structure changes may require updates to the selectors in
	`src/job_pipeline/scraper.py`.
- Use the included sample HTML files when developing parser changes so live
	requests are not required for every test.
