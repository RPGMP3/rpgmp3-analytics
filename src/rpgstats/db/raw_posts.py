# src/rpgstats/db/raw_posts.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from rpgstats.db.connect import get_conn


@dataclass
class RawPostRow:
    url: str
    lastmod: Optional[datetime]


def get_posts_needing_extract(limit: int) -> list[RawPostRow]:
    """
    Fetch a batch of URLs that still need metadata extraction.

    We include rows missing any of:
    - duration_seconds
    - tags
    - author
    - group_name
    - system_name
    - campaign_name

    Ordered by lastmod desc so we tend to process recent posts first.
    """
    sql = """
    select url, lastmod
    from raw_posts
    where duration_seconds is null
       or tags is null
       or author is null
       or group_name is null
       or group_name = ''
       or system_name is null
       or system_name = ''
       or campaign_name is null
       or campaign_name = ''
    order by lastmod desc nulls last
    limit %s
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()

    return [RawPostRow(url=r[0], lastmod=r[1]) for r in rows]


def update_post_extracted(
    url: str,
    title: str | None,
    author: str | None,
    published_at: datetime | None,
    tags: list[str] | None,
    group_name: str | None,
    system_name: str | None,
    campaign_name: str | None,
    duration_seconds: int | None,
    download_url: str | None,
    file_size_bytes: int | None,
    youtube_urls: list[str] | None,
) -> None:
    """
    Update raw_posts with extracted values.

    Notes:
    - Uses COALESCE so we don't overwrite existing values with NULL.
    - Uses NULLIF for text fields so empty strings don't block later backfills.
    - Casts numeric placeholders (::int, ::bigint) to avoid Postgres type inference
      errors when values are NULL.
    """
    sql = """
    update raw_posts
    set title = coalesce(nullif(%s, ''), title),
        author = coalesce(nullif(%s, ''), author),
        published_at = coalesce(%s, published_at),
        tags = coalesce(%s, tags),

        group_name = coalesce(nullif(%s, ''), group_name),
        system_name = coalesce(nullif(%s, ''), system_name),
        campaign_name = coalesce(nullif(%s, ''), campaign_name),

        duration_seconds = coalesce(%s::int, duration_seconds),
        duration_source = case
            when %s::int is null then duration_source
            else 'wp_html'
        end,

        download_url = coalesce(nullif(%s, ''), download_url),
        file_size_bytes = coalesce(%s::bigint, file_size_bytes),
        youtube_urls = coalesce(%s, youtube_urls)

    where url = %s
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    title,
                    author,
                    published_at,
                    tags,
                    group_name,
                    system_name,
                    campaign_name,
                    duration_seconds,
                    duration_seconds,
                    download_url,
                    file_size_bytes,
                    youtube_urls,
                    url,
                ),
            )
        conn.commit()

