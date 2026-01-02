from typing import Iterable
from datetime import datetime
import httpx
from lxml import etree


def fetch_sitemap(url: str) -> Iterable[tuple[str, datetime | None]]:
    """
    Fetch a WordPress sitemap and yield (loc, lastmod).
    """
    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()

    root = etree.fromstring(resp.content)

    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    for url_el in root.findall("ns:url", ns):
        loc = url_el.findtext("ns:loc", namespaces=ns)
        lastmod_text = url_el.findtext("ns:lastmod", namespaces=ns)

        lastmod = None
        if lastmod_text:
            try:
                lastmod = datetime.fromisoformat(lastmod_text.replace("Z", "+00:00"))
            except ValueError:
                pass

        if loc:
            yield loc.strip(), lastmod

