# src/rpgstats/analytics/stats.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rpgstats.db.connect import get_conn


@dataclass
class StatsSummary:
    total_posts: int
    with_duration: int
    missing_duration: int
    total_hours_all: float
    total_hours_sessions: float


def get_summary() -> StatsSummary:
    """
    Session heuristic:
      URL contains session-<number> (case-insensitive)
    """
    sql = """
    select
      count(*)::int as total_posts,
      count(*) filter (where duration_seconds is not null)::int as with_duration,
      count(*) filter (where duration_seconds is null)::int as missing_duration,
      coalesce(sum(duration_seconds) / 3600.0, 0)::float as total_hours_all,
      coalesce(sum(duration_seconds) filter (where url ~* 'session-[0-9]+') / 3600.0, 0)::float as total_hours_sessions
    from raw_posts;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()

    return StatsSummary(
        total_posts=row[0],
        with_duration=row[1],
        missing_duration=row[2],
        total_hours_all=float(row[3]),
        total_hours_sessions=float(row[4]),
    )


def top_groups_by_hours(limit: int = 10) -> list[tuple[str, float, int]]:
    """
    Returns (group_name, hours, episodes_with_duration)
    """
    sql = """
    select
      coalesce(group_name, '(unknown)') as group_name,
      (sum(duration_seconds) / 3600.0)::float as hours,
      count(*)::int as items
    from raw_posts
    where duration_seconds is not null
      and url ~* 'session-[0-9]+'
    group by 1
    order by hours desc
    limit %s;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    return [(r[0], float(r[1]), int(r[2])) for r in rows]


def top_authors_by_hours(limit: int = 10) -> list[tuple[str, float, int]]:
    """
    Returns (author, hours, episodes_with_duration)
    """
    sql = """
    select
      coalesce(author, '(unknown)') as author,
      (sum(duration_seconds) / 3600.0)::float as hours,
      count(*)::int as items
    from raw_posts
    where duration_seconds is not null
      and url ~* 'session-[0-9]+'
    group by 1
    order by hours desc
    limit %s;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    return [(r[0], float(r[1]), int(r[2])) for r in rows]


def missing_duration_urls(limit: int = 25) -> list[tuple[str, Optional[str], Optional[str]]]:
    """
    Rows that look like session posts but are missing duration.
    Returns (url, title, group_name)
    """
    sql = """
    select url, title, group_name
    from raw_posts
    where duration_seconds is null
      and url ~* 'session-[0-9]+'
    order by lastmod desc nulls last
    limit %s;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    return [(r[0], r[1], r[2]) for r in rows]

