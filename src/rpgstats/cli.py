from pathlib import Path
import time

import httpx
import typer
from rich import print

from rpgstats.db.connect import get_conn
from rpgstats.crawl.sitemap import fetch_sitemap
from rpgstats.db.upsert import upsert_raw_post

from rpgstats.db.raw_posts import get_posts_needing_extract, update_post_extracted
from rpgstats.crawl.extract_post import extract_post_fields

from rpgstats.analytics.stats import (
    get_summary,
    top_groups_by_hours,
    top_authors_by_hours,
    missing_duration_urls,
)

app = typer.Typer(help="RPGMP3 analytics CLI")


@app.callback()
def main():
    """
    Tools for crawling RPGMP3 and generating analytics.
    """
    pass


@app.command("db-init")
def db_init():
    """Initialize the database schema."""
    schema_path = Path(__file__).parent / "db" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    print("[green]DB initialized successfully.[/green]")


@app.command("crawl-sitemap")
def crawl_sitemap(url: str):
    """
    Ingest URLs from a sitemap into raw_posts.
    """
    count = 0

    for loc, lastmod in fetch_sitemap(url):
        upsert_raw_post(loc, lastmod)
        count += 1

        if count % 100 == 0:
            print(f"[cyan]Ingested {count} URLs...[/cyan]")

    print(f"[green]Done. Ingested {count} URLs.[/green]")


def _run_extract_batch(client: httpx.Client, limit: int, sleep_ms: int) -> tuple[int, int]:
    """
    Run a single extraction batch.

    Returns: (processed_count, updated_count)
    """
    rows = get_posts_needing_extract(limit)
    if not rows:
        return 0, 0

    updated = 0
    for i, row in enumerate(rows, start=1):
        try:
            resp = client.get(row.url)
            resp.raise_for_status()

            ex = extract_post_fields(resp.text, url=row.url)

            update_post_extracted(
                url=row.url,
                title=ex.title,
                author=ex.author,
                published_at=ex.published_at,
                tags=ex.tags,
                group_name=ex.group_name,
                system_name=ex.system_name,
                campaign_name=ex.campaign_name,
                duration_seconds=ex.duration_seconds,
                download_url=ex.download_url,
                file_size_bytes=ex.file_size_bytes,
                youtube_urls=ex.youtube_urls,
            )

            updated += 1
            print(
                f"[green]{i}/{len(rows)}[/green] "
                f"{row.url} "
                f"dur={ex.duration_seconds} "
                f"group={ex.group_name} "
                f"system={ex.system_name} "
                f"campaign={ex.campaign_name}"
            )

        except Exception as e:
            print(f"[red]{i}/{len(rows)}[/red] {row.url} -> error: {e}")

        time.sleep(sleep_ms / 1000)

    return len(rows), updated


@app.command("extract-posts")
def extract_posts(
    limit: int = 50,
    sleep_ms: int = 400,
    repeat: int = 1,
    until_empty: bool = typer.Option(False, "--until-empty", help="Keep running batches until no rows remain."),
    max_pages: int = typer.Option(0, "--max-pages", help="Hard cap on total pages processed (0 = no cap)."),
):
    """
    Fetch post pages and extract structured fields (duration, author, tags, group, system, campaign, etc).

    By default runs one batch.
    Use --repeat N to run N batches.
    Use --until-empty to keep going until there's nothing left to extract.
    Use --max-pages to prevent runaway long runs.
    """
    if until_empty:
        repeat = 10**9

    client = httpx.Client(
        timeout=30,
        headers={"User-Agent": "rpgstats/0.1 (capstone; +https://github.com/<you>/rpgmp3-analytics)"},
        follow_redirects=True,
    )

    total_processed = 0
    total_updated = 0

    for batch_num in range(1, repeat + 1):
        if max_pages and total_processed >= max_pages:
            print(f"[yellow]Reached --max-pages={max_pages}. Stopping.[/yellow]")
            break

        print(f"\n[bold]Batch {batch_num}[/bold] (limit={limit}, sleep_ms={sleep_ms})")
        processed, updated = _run_extract_batch(client, limit=limit, sleep_ms=sleep_ms)

        total_processed += processed
        total_updated += updated

        print(
            f"[cyan]Batch {batch_num} done:[/cyan] processed={processed}, updated={updated} | "
            f"total_processed={total_processed}, total_updated={total_updated}"
        )

        if processed == 0:
            print("[green]No posts needing extraction. Done 🎉[/green]")
            break

        if max_pages and total_processed >= max_pages:
            print(f"[yellow]Reached --max-pages={max_pages}. Stopping.[/yellow]")
            break

    print(f"\n[bold green]Extraction complete.[/bold green] total_processed={total_processed}, total_updated={total_updated}\n")


@app.command("stats")
def stats(limit: int = 10):
    """
    Print a terminal stats report (sessions are inferred by URL containing session-<number>).
    """
    s = get_summary()

    print("\n[bold]RPGMP3 Stats[/bold]")
    print(f"Total posts: [bold]{s.total_posts}[/bold]")
    print(f"With duration: [bold]{s.with_duration}[/bold]")
    print(f"Missing duration: [bold]{s.missing_duration}[/bold]")
    print(f"Total hours (all content with duration): [bold]{s.total_hours_all:.2f}[/bold]")
    print(f"Total hours (sessions only, heuristic): [bold]{s.total_hours_sessions:.2f}[/bold]\n")

    print(f"[bold]Top Groups by Session Hours (limit {limit})[/bold]")
    for name, hours, items in top_groups_by_hours(limit):
        print(f"- {name}: {hours:.2f} hours ({items} items)")

    print(f"\n[bold]Top Authors by Session Hours (limit {limit})[/bold]")
    for name, hours, items in top_authors_by_hours(limit):
        print(f"- {name}: {hours:.2f} hours ({items} items)")
    print("")


@app.command("report-missing-durations")
def report_missing_durations(limit: int = 25):
    """
    Show session-like URLs missing duration_seconds (good for debugging extraction gaps).
    """
    rows = missing_duration_urls(limit)
    print(f"\n[bold]Session-like posts missing duration (limit {limit})[/bold]")

    if not rows:
        print("[green]None found 🎉[/green]\n")
        return

    for url, title, group in rows:
        t = title or "(no title yet)"
        g = group or "(unknown group)"
        print(f"- {t} | {g}\n  {url}")

    print("")


if __name__ == "__main__":
    app()

