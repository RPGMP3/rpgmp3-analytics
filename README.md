# RPGMP3 Analytics

RPGMP3 Analytics is a command-line analytics pipeline for the RPGMP3 actual play archive. It ingests post URLs from a WordPress sitemap, crawls each post page, extracts and normalizes metadata, stores the results in Postgres, and produces terminal-based reports summarizing thousands of hours of tabletop RPG recordings.

---

## Motivation

Podcast RSS feeds typically expose only the most recent few hundred episodes, which makes them unsuitable for analyzing long-running archives. RPGMP3 hosts decades of actual play content across many groups, systems, and campaigns, and understanding that history requires crawling and normalizing the full site rather than relying on podcast feeds alone.

This project exists to answer questions such as:

- How many total hours of actual play exist in the archive?
- Which groups, systems, and campaigns account for the most play time?
- How does activity vary across contributors and game systems over time?

The goal is to build a repeatable, inspectable analytics pipeline that works against real-world, imperfect data and can evolve as the site changes.

---

## Quick Start

The Quick Start demonstrates the full pipeline end-to-end with minimal configuration.

### Requirements

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv)
- Docker (for Postgres)
- A local Postgres database

### Clone and install

```bash
git clone https://github.com/<your-username>/rpgmp3-analytics.git
cd rpgmp3-analytics
uv pip install -e .

## Start Postgres (Docker example)
docker run --name rpgstats-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=rpgstats \
  -p 5432:5432 \
  -d postgres:16

## Configure environment
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/rpgstats"

## Initialize the database schema
uv run python -m rpgstats.cli db-init

## Ingest the RPGMP3 post sitemap
uv run python -m rpgstats.cli crawl-sitemap \
  https://www.rpgmp3.com/post-sitemap.xml

## Extract metadata from posts 
Run extraction in batches until the queue is empty:
uv run python -m rpgstats.cli extract-posts \
  --limit 200 \
  --sleep-ms 200 \
  --until-empty

## View analytics
uv run python -m rpgstats.cli stats --limit 15

## Usage
The Usage section documents advanced workflows and operational details beyond the initial run.

### Incremental extraction
Extraction is designed to be incremental and idempotent. Each post is marked as attempted after extraction, which prevents infinite retry loops on posts that cannot be fully parsed. Extraction can safely be stopped and resumed at any time.

Batch size and crawl delay are configurable to control load on the source site:
uv run python -m rpgstats.cli extract-posts \
  --limit 100 \
  --sleep-ms 500

### Targeted re-extraction
When extraction logic is improved or content on the site is updated, individual posts or subsets of posts can be reprocessed by clearing their extraction marker in the database and re-running extraction.

Example: reprocess posts missing duration data.
update raw_posts
set extracted_at = null
where duration_seconds is null;

Then:

uv run python -m rpgstats.cli extract-posts --until-empty

### Reporting and data quality
The stats command reports both aggregate metrics and data quality indicators.

“Sessions only” runtime is calculated using a URL heuristic (session-<number>) and represents authoritative playtime.

“All content” runtime excludes posts tagged as Journals or Blog entries to avoid inflating totals with non-audio content.

Missing data is surfaced explicitly rather than hidden.

This makes it clear which numbers are definitive and which are best-effort.

### Heuristics and normalization
Group and system names are inferred using curated lists stored in:

src/rpgstats/data/groups.txt

src/rpgstats/data/systems.txt

Campaign names are inferred from tags, URL slugs, and titles, then cleaned to remove recording artifacts such as session numbers or part suffixes.

Known campaign naming variants are normalized using:
src/rpgstats/data/campaign_aliases.txt

Format:
FROM => TO

Example:
Curse Of The Crimson Throne => Curse of the Crimson Throne
Inquisition Of Blood => Inquisition of Blood

This approach avoids brittle heuristics and keeps normalization explicit and auditable.

## Contributing
This project is structured to be easy to run and modify locally.

### Local development

Clone the repository, install it in editable mode, and run a local Postgres instance as described in the Quick Start. Most development work involves iterating on extraction logic or reporting queries.

After making changes to extraction, reset extraction markers for affected rows and re-run the extractor to validate the results.

### Tests

This project does not currently include an automated test suite. Validation is performed by re-running extraction and inspecting reporting output and data quality metrics.

### Submitting changes

If you would like to contribute:

Fork the repository

Create a feature branch from main

Make focused, well-scoped changes

Open a pull request against main

Clear commit messages and small, reviewable changes are preferred.

## Notes
The analytics produced by this project reflect the current state of the RPGMP3 site and evolve as content and tagging change. The pipeline is designed to surface inconsistencies and make corrections explicit rather than silently discarding data.
