# src/rpgstats/crawl/extract_post.py

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# Matches: Duration: 2:08:54 OR Duration: 48:12
DURATION_RE = re.compile(r"Duration:\s*([0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?)", re.IGNORECASE)
# Matches: — 69.6MB or - 69.6MB
SIZE_RE = re.compile(r"[—-]\s*([0-9.]+)\s*(KB|MB|GB)\b", re.IGNORECASE)
PAREN_RE = re.compile(r"\(([^)]+)\)")
SESSION_NUM_RE = re.compile(r"\bSession\s+\d+\b", re.IGNORECASE)
SLUG_SESSION_RE = re.compile(r"-session-\d+/?$", re.IGNORECASE)

# Remove recording artifacts from inferred campaign names
BAD_CAMPAIGN_SUFFIX_RE = re.compile(
    r"""
    \b(
        session\s*\d+[a-z]? |      # Session 44, Session 03a
        part\s*\d+ |               # Part 2
        character\s+creation |     # Character Creation
        sfx |                      # Sfx
        \d+[a-z]?                  # trailing 2, b, 03a
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# If we ever infer a "campaign" that is exactly one of these, drop it.
# (This is conservative; feel free to add more later.)
BAD_CAMPAIGN_EXACT = {
    "session",
    "part",
}


def _hms_to_seconds(s: str) -> int:
    parts = s.split(":")
    if len(parts) == 2:
        m, sec = parts
        return int(m) * 60 + int(sec)
    if len(parts) == 3:
        h, m, sec = parts
        return int(h) * 3600 + int(m) * 60 + int(sec)
    raise ValueError(f"Bad duration: {s}")


def _size_to_bytes(num: float, unit: str) -> int:
    unit = unit.upper()
    mult = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}[unit]
    return int(num * mult)


def _data_path(filename: str) -> Path:
    # this file: src/rpgstats/crawl/extract_post.py
    # data dir:  src/rpgstats/data/
    return Path(__file__).resolve().parents[1] / "data" / filename


def _read_list_file(filename: str) -> list[str]:
    """
    Read a list file from src/rpgstats/data/<filename>, one item per line.
    Lines starting with # are ignored.
    """
    path = _data_path(filename)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def load_known_groups() -> list[str]:
    return _read_list_file("groups.txt")


def load_known_systems() -> list[str]:
    return _read_list_file("systems.txt")


def load_campaign_aliases() -> dict[str, str]:
    """
    Load campaign aliases from src/rpgstats/data/campaign_aliases.txt

    Format:
      FROM => TO

    Matching is case-insensitive on FROM.
    """
    path = _data_path("campaign_aliases.txt")
    if not path.exists():
        return {}

    aliases: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=>" not in line:
            continue
        left, right = line.split("=>", 1)
        frm = left.strip()
        to = right.strip()
        if frm and to:
            aliases[frm.casefold()] = to
    return aliases


def normalize_campaign_name(name: str | None) -> str | None:
    """
    Normalize campaign name using campaign_aliases.txt (if present).
    """
    if not name:
        return None
    aliases = load_campaign_aliases()
    if not aliases:
        return name
    return aliases.get(name.casefold(), name)


def clean_campaign_name(name: str | None) -> str | None:
    """
    Remove recording artifacts like:
      "Kingmaker Session 44 2" -> "Kingmaker"
      "The One Ring ... Session 03a" -> "The One Ring ..."
      "Session 00 Character Creation" -> "" (None)
    """
    if not name:
        return None

    cleaned = BAD_CAMPAIGN_SUFFIX_RE.sub("", name)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -–—:")

    if not cleaned:
        return None

    if cleaned.casefold() in BAD_CAMPAIGN_EXACT:
        return None

    # Too-short campaign names after cleaning usually mean "we stripped everything useful"
    if len(cleaned) < 3:
        return None

    return cleaned


def infer_group_name(tags: list[str] | None, page_text: str | None = None) -> str | None:
    known = load_known_groups()
    if not known:
        return None

    haystacks: list[tuple[str, int]] = []
    if tags:
        for t in tags:
            haystacks.append((t, 3))
            for m in PAREN_RE.findall(t):
                haystacks.append((m, 3))
    if page_text:
        haystacks.append((page_text, 1))

    scores: dict[str, int] = {g: 0 for g in known}
    for g in known:
        g_low = g.lower()
        for h, weight in haystacks:
            h_low = h.lower()
            if h_low == g_low:
                scores[g] += 10
            elif g_low in h_low:
                scores[g] += weight

    best_name, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_name if best_score > 0 else None


def infer_system_name(tags: list[str] | None, page_text: str | None = None) -> str | None:
    known = load_known_systems()
    if not known:
        return None

    haystacks: list[tuple[str, int]] = []
    if tags:
        for t in tags:
            haystacks.append((t, 3))
            for m in PAREN_RE.findall(t):
                haystacks.append((m, 3))
    if page_text:
        haystacks.append((page_text, 1))

    scores: dict[str, int] = {s: 0 for s in known}
    for sys in known:
        sys_low = sys.lower()
        for h, weight in haystacks:
            h_low = h.lower()
            if h_low == sys_low:
                scores[sys] += 10
            elif sys_low in h_low:
                scores[sys] += weight

    best_name, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_name if best_score > 0 else None


def infer_campaign_from_url(url: str | None) -> str | None:
    """
    Derive campaign name from URL slug when it looks like:
      https://.../<campaign>-session-123/
    Example:
      giantslayer-session-16 -> Giantslayer
      kingmaker-session-101  -> Kingmaker
    """
    if not url:
        return None

    path = urlparse(url).path.strip("/")
    if not path:
        return None

    slug = path.split("/")[-1].lower().strip()
    slug = SLUG_SESSION_RE.sub("", slug).strip("-")
    if not slug:
        return None

    words = [w for w in slug.split("-") if w]
    if not words:
        return None

    # Titlecase each hyphen-word; keeps things readable without overfitting
    return " ".join(w.capitalize() for w in words)


def infer_campaign_name(
    tags: list[str] | None,
    title: str | None,
    group_name: str | None,
    system_name: str | None,
    url: str | None,
) -> str | None:
    """
    Best-effort campaign inference.

    Strategy:
    1) If tags contain "Campaign (Group)", return Campaign — BUT skip if Campaign == system_name
    2) If URL looks like "<campaign>-session-123", use that
    3) Title fallback: strip "Session ###"
    """
    sys_low = system_name.lower() if system_name else None
    gn_low = group_name.lower() if group_name else None

    # 1) Group-scoped tag pattern: "Campaign Name (Group Name)"
    if tags and group_name:
        for t in tags:
            parens = PAREN_RE.findall(t)
            if any(p.strip().lower() == gn_low for p in parens):
                cleaned = PAREN_RE.sub("", t).strip()

                # Don't treat "System (Group)" as a campaign
                if sys_low and cleaned.lower() == sys_low:
                    continue
                if gn_low and cleaned.lower() == gn_low:
                    continue

                if cleaned:
                    return cleaned

    # 2) URL fallback (great for Giantslayer/Kingmaker/etc.)
    from_url = infer_campaign_from_url(url)
    if from_url:
        if sys_low and from_url.lower() == sys_low:
            pass
        else:
            return from_url

    # 3) Title fallback: strip "Session NNN"
    if title:
        candidate = SESSION_NUM_RE.sub("", title).strip()
        candidate = re.sub(r"\s{2,}", " ", candidate).strip(" -–—:")
        if candidate:
            if sys_low and candidate.lower() == sys_low:
                return None
            return candidate

    return None


@dataclass
class PostExtract:
    title: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    tags: Optional[list[str]] = None

    group_name: Optional[str] = None
    system_name: Optional[str] = None
    campaign_name: Optional[str] = None

    duration_seconds: Optional[int] = None
    download_url: Optional[str] = None
    file_size_bytes: Optional[int] = None

    youtube_urls: Optional[list[str]] = None


def extract_post_fields(html: str, url: str | None = None) -> PostExtract:
    soup = BeautifulSoup(html, "lxml")
    out = PostExtract()

    # Title
    h1 = soup.find("h1")
    if h1:
        out.title = h1.get_text(strip=True)

    # Published date (often <time datetime="...">)
    t = soup.find("time")
    if t and t.has_attr("datetime"):
        try:
            out.published_at = datetime.fromisoformat(t["datetime"].replace("Z", "+00:00"))
        except ValueError:
            pass

    # Author (common WP patterns)
    a = (
        soup.find("a", attrs={"rel": "author"})
        or soup.select_one(".author a")
        or soup.select_one(".entry-author a")
    )
    if a:
        out.author = a.get_text(strip=True)

    # Tags / categories (best-effort across themes)
    tag_texts: list[str] = []
    selectors = [
        ".cat-links a",
        ".tags-links a",
        "a[rel='category tag']",
        ".post-meta a",
        ".entry-meta a",
        ".td-post-category a",
        ".td-post-source-tags a",
    ]

    for sel in selectors:
        for el in soup.select(sel):
            txt = el.get_text(strip=True)
            if not txt:
                continue
            low = txt.lower()
            if low in {
                "download",
                "play",
                "rss",
                "spotify",
                "apple podcasts",
                "amazon music",
                "pandora",
                "iheartradio",
                "podchaser",
                "tunein",
            }:
                continue
            tag_texts.append(txt)

    out.tags = sorted(set(tag_texts)) if tag_texts else None

    # Download link + duration + filesize
    download_a = None
    for link in soup.find_all("a"):
        if link.get_text(" ", strip=True).lower() == "download":
            download_a = link
            break

    if download_a and download_a.has_attr("href"):
        out.download_url = download_a["href"].strip()
        container_text = (
            download_a.parent.get_text(" ", strip=True)
            if download_a.parent
            else soup.get_text(" ", strip=True)
        )

        m = DURATION_RE.search(container_text)
        if m:
            out.duration_seconds = _hms_to_seconds(m.group(1))

        s = SIZE_RE.search(container_text)
        if s:
            out.file_size_bytes = _size_to_bytes(float(s.group(1)), s.group(2))

    # YouTube embeds
    yts: list[str] = []
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if "youtube.com" in src or "youtu.be" in src:
            yts.append(src)
    out.youtube_urls = sorted(set(yts)) if yts else None

    # Group/System/Campaign inference + cleanup + alias normalization
    page_text = soup.get_text(" ", strip=True)
    out.group_name = infer_group_name(out.tags, page_text)
    out.system_name = infer_system_name(out.tags, page_text)

    raw_campaign = infer_campaign_name(out.tags, out.title, out.group_name, out.system_name, url)
    cleaned_campaign = clean_campaign_name(raw_campaign)
    out.campaign_name = normalize_campaign_name(cleaned_campaign)

    return out

