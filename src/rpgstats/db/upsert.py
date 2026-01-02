from datetime import datetime
from rpgstats.db.connect import get_conn


def upsert_raw_post(url: str, lastmod: datetime | None):
    sql = """
    insert into raw_posts (url, lastmod)
    values (%s, %s)
    on conflict (url) do update
      set lastmod = excluded.lastmod
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (url, lastmod))
        conn.commit()

