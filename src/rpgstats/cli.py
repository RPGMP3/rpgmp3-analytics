from pathlib import Path
from datetime import datetime
import typer
from rich import print

from rpgstats.db.connect import get_conn
from rpgstats.crawl.sitemap import fetch_sitemap
from rpgstats.db.upsert import upsert_raw_post

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


if __name__ == "__main__":
    app()

