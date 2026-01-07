# RPGMP3 Analytics (rpgstats)

A small analytics pipeline for the RPGMP3 actual play archive.

It ingests RPGMP3 post URLs from the WordPress post sitemap, crawls each post page, extracts useful metadata (duration, author, tags, group, system, campaign), stores everything in Postgres, and prints terminal reports showing totals and “top” rankings.

This project exists because podcast RSS feeds often only contain the most recent ~300 episodes, while the RPGMP3 archive spans thousands of posts and decades of content.

## What it does

### Ingest
- Reads URLs from the RPGMP3 WordPress post sitemap
- Upserts them into Postgres (`raw_posts`)

### Extract
For each post URL, fetches the page HTML and attempts to extract:
- Title
- Author
- Last modified time (from sitemap)
- Tags/categories
- Audio duration (from the embedded “Download (Duration: …)” line)
- Group name (heuristic based on known group names)
- System name (heuristic based on known systems)
- Campaign name (heuristic + cleanup; optional alias mapping)

### Report
Outputs terminal stats including:
- Total runtime (all audio content, excluding Journals/Blog content)
- Total runtime (sessions only, heuristic)
- Top groups/authors/systems/campaigns by total hours
- Top group+system and group+campaign pairs

## Example output

(Your totals will vary over time as the site grows.)

- Total runtime (sessions only): **34 weeks** of continuous audio
- Total runtime (all audio content, excluding Journals/Blog): **36 weeks** of continuous audio

## Project layout

- `src/rpgstats/cli.py`  
  Typer CLI entrypoint
- `src/rpgstats/crawl/sitemap.py`  
  Sitemap ingestion
- `src/rpgstats/crawl/extract_post.py`  
  HTML extraction + heuristics (group/system/campaign, duration parsing)
- `src/rpgstats/analytics/stats.py`  
  SQL-backed reporting queries
- `src/rpgstats/db/schema.sql`  
  Database schema
- `src/rpgstats/data/`  
  Heuristic lists:
  - `groups.txt`
  - `systems.txt`
  - `campaign_aliases.txt` (optional)

## Requirements

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv)
- Docker (for Postgres)
- A `DATABASE_URL` pointing to your Postgres database

## Setup

### 1) Clone and install
```bash
uv pip install -e .

2) Run Postgres (Docker)
Example (adjust as needed):

docker run --name rpgstats-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=rpgstats \
  -p 5432:5432 \
  -d postgres:16
3) Configure environment
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/rpgstats"
4) Initialize schema

uv run python -m rpgstats.cli db-init

Usage
Ingest URLs from the sitemap

uv run python -m rpgstats.cli ingest-sitemap --sitemap-url "https://www.rpgmp3.com/post-sitemap.xml"

Extract metadata from posts
Run extraction in batches until the queue is empty:

uv run python -m rpgstats.cli extract-posts --limit 200 --sleep-ms 200 --until-empty

Print stats report

uv run python -m rpgstats.cli stats --limit 15
Notes on heuristics
Sessions-only heuristic
A post is considered “session-like” if the URL matches:

session-<number> (case-insensitive)

This is used to generate the “sessions only” runtime and rankings.

Excluding Journals/Blog content from “all content” runtime
Some posts are not audio episodes (journals, blog posts, guides, etc.). The “all content” runtime totals exclude any post tagged:

Journals / Journal

Blog / Blogs

(These exclusions are applied in reporting.)

Campaign cleanup and aliasing
Campaign names are inferred from tags / URL slug / title. A cleanup pass removes artifacts like “Session 44 2”.

For rare naming/casing variations, you can add canonical mappings in:

src/rpgstats/data/campaign_aliases.txt

Format:
FROM => TO

Example:
Curse Of The Crimson Throne => Curse of the Crimson Throne
Inquisition Of Blood => Inquisition of Blood

Future improvements

Export reports to CSV/JSON

Add a small web UI/dashboard

Improve campaign inference using a curated tag export from WordPress

Add incremental scheduled ingestion/extraction


