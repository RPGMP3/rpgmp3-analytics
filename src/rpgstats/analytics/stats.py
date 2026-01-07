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

    total_seconds_all: int
    total_seconds_sessions: int

    total_hours_all: float
    total_hours_sessions: float


def get_summary() -> StatsSummary:
    """
    Session heuristic:
      URL contains session-<number> (case-insensitive)

    "All content" totals + with/missing duration counts exclude posts tagged:
      - Journal / Journals
      - Blog / Blogs

    (This prevents blog/journal content from polluting the audio-runtime numbers.)
    """
    sql = """
    with excluded as (
      select url
      from raw_posts
      where exists (
        select 1
        from unnest(coalesce(tags, array[]::text[])) t(tag)
        where lower(t.tag) in ('journal','journals','blog','blogs')
      )
    )
    select
      count(*)::int as total_posts,

      count(*) filter (
        where url not in (select url from excluded)
          and duration_seconds is not null
      )::int as with_duration,

      count(*) filter (
        where url not in (select url from excluded)
          and duration_seconds is null
      )::int as missing_duration,

      coalesce(sum(duration_seconds) filter (
        where url not in (select url from excluded)
      ), 0)::bigint as total_seconds_all,

      coalesce(sum(duration_seconds) filter (
        where url ~* 'session-[0-9]+'
      ), 0)::bigint as total_seconds_sessions,

      coalesce(sum(duration_seconds) filter (
        where url not in (select url from excluded)
      ) / 3600.0, 0)::float as total_hours_all,

      coalesce(sum(duration_seconds) filter (
        where url ~* 'session-[0-9]+'
      ) / 3600.0, 0)::float as total_hours_sessions
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
        total_seconds_all=int(row[3]),
        total_seconds_sessions=int(row[4]),
        total_hours_all=float(row[5]),
        total_hours_sessions=float(row[6]),
    )


def top_groups_by_hours(limit: int = 10) -> list[tuple[str, float, int]]:
    """
    Returns (group_name, hours, items_with_duration)
    (sessions only)
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
    Returns (author, hours, items_with_duration)
    (sessions only)
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
    Rows that look like session posts but are missing duration_seconds.
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


def top_systems_by_hours(limit: int = 15) -> list[tuple[str, float, int]]:
    """
    Returns (system_name, hours, session_count) for session-like posts.
    """
    sql = """
    select
      coalesce(system_name, '(unknown)') as system_name,
      (sum(duration_seconds) / 3600.0)::float as hours,
      count(*)::int as sessions
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


def top_systems_by_count(limit: int = 15) -> list[tuple[str, int, float]]:
    """
    Returns (system_name, session_count, hours) for session-like posts.
    """
    sql = """
    select
      coalesce(system_name, '(unknown)') as system_name,
      count(*)::int as sessions,
      (sum(duration_seconds) / 3600.0)::float as hours
    from raw_posts
    where duration_seconds is not null
      and url ~* 'session-[0-9]+'
    group by 1
    order by sessions desc
    limit %s;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    return [(r[0], int(r[1]), float(r[2])) for r in rows]


def top_group_system_pairs(limit: int = 20) -> list[tuple[str, str, float, int]]:
    """
    Returns (group_name, system_name, hours, sessions) for session-like posts.
    """
    sql = """
    select
      coalesce(group_name, '(unknown)') as group_name,
      coalesce(system_name, '(unknown)') as system_name,
      (sum(duration_seconds) / 3600.0)::float as hours,
      count(*)::int as sessions
    from raw_posts
    where duration_seconds is not null
      and url ~* 'session-[0-9]+'
    group by 1, 2
    order by hours desc
    limit %s;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    return [(r[0], r[1], float(r[2]), int(r[3])) for r in rows]


def top_campaigns_by_hours(limit: int = 15) -> list[tuple[str, float, int]]:
    """
    Overall campaigns by hours (across all groups).
    Returns (campaign_name, hours, sessions)
    """
    sql = """
    select
      campaign_name,
      (sum(duration_seconds) / 3600.0)::float as hours,
      count(*)::int as sessions
    from raw_posts
    where duration_seconds is not null
      and url ~* 'session-[0-9]+'
      and campaign_name is not null
      and campaign_name <> ''
    group by 1
    order by hours desc
    limit %s;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    return [(r[0], float(r[1]), int(r[2])) for r in rows]


def top_group_campaign_pairs(limit: int = 20) -> list[tuple[str, str, float, int]]:
    """
    Campaigns per group by hours.
    Returns (group_name, campaign_name, hours, sessions)
    """
    sql = """
    select
      coalesce(group_name, '(unknown)') as group_name,
      campaign_name,
      (sum(duration_seconds) / 3600.0)::float as hours,
      count(*)::int as sessions
    from raw_posts
    where duration_seconds is not null
      and url ~* 'session-[0-9]+'
      and campaign_name is not null
      and campaign_name <> ''
    group by 1, 2
    order by hours desc
    limit %s;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    return [(r[0], r[1], float(r[2]), int(r[3])) for r in rows]

