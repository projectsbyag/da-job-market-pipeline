![STEM labor market dashboard](docs/dashboard.png)

# DA Job Market Pipeline

A small job-market data pipeline that collects STEM job postings from
[MyJobMag](https://www.myjobmag.com), extracts useful fields and skill flags,
and stores the results in SQLite or PostgreSQL.

## Features

- Scrapes Data & AI, Software, Cybersecurity, Cloud & DevOps, QA and Engineering roles.
- Adds remote international STEM roles from the public Arbeitnow job feed.
- Extracts title, company, location, description and posting date.
- Detects SQL, Python, Tableau and Power BI keywords.
- Deduplicates records by job URL.
- Provides a FastAPI service and responsive dashboard for querying jobs and triggering scrapes.
- Supports scheduled scraping through GitHub Actions and a Render deployment.

## Project layout

```text
.
├── app.py                         # FastAPI application and API routes
├── data/raw/                      # Sample HTML fixtures
├── requirements.txt
├── static/dashboard.html          # Responsive STEM dashboard
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

Returns the newest saved postings. `limit` accepts values from 1 to 500. Use
`category` to filter by STEM family and `q` to search titles or companies.

```http
GET /api/jobs?category=Software&q=engineer&limit=50
```

### STEM categories

```http
GET /api/categories
```

Returns the configured STEM families and their search terms.

### Trigger a scrape

```bash
curl -X POST \
  "http://127.0.0.1:8000/api/scrape?pages=1&location=lagos"
```

Without a `keyword`, the endpoint runs the full STEM sweep. Pass `category` to
run one family or pass `keyword` for a custom single query. The response
contains the number of records parsed, inserted and skipped as duplicates.
`pages` accepts values from 1 to 10.

### Dashboard

`GET /` serves the dashboard. It provides category and location controls, a
STEM sweep action, coverage metrics, title/company search and direct links to
the source listings.

The dashboard is designed as a STEM labor-market control room: choose a search
scope and location, run a sweep, then review open signals, fresh postings and
coverage across Data & AI, Software, Cybersecurity, Cloud & DevOps, QA &
Testing, Engineering and international remote roles.

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
- The international feed is filtered to remote roles with STEM-related terms;
	its availability depends on the public Arbeitnow API.
- Use the included sample HTML files when developing parser changes so live
	requests are not required for every test.