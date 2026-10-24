"""Fetch acquisition-related announcements from CNINFO (巨潮资讯网), the CSRC-designated
disclosure site for Shanghai, Shenzhen and Beijing listed companies.

Uses the same full-text search endpoint as the public website. Be polite: small pages,
a pause between requests, and run it as a daily batch, not on every page view.
"""

import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx

QUERY_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
PDF_BASE = "http://static.cninfo.com.cn/"

# Titles that signal acquisition appetite. Searched one at a time.
DEFAULT_KEYWORDS = ["收购", "购买资产", "并购", "受让股权", "重大资产重组"]

_TAG = re.compile(r"</?em>")


@dataclass(frozen=True)
class Announcement:
    sec_code: str
    sec_name: str
    title: str
    published_at: datetime
    url: str
    announcement_id: str


def parse(payload: dict) -> list[Announcement]:
    out = []
    for row in payload.get("announcements") or []:
        out.append(
            Announcement(
                sec_code=row["secCode"],
                sec_name=row["secName"],
                title=_TAG.sub("", row["announcementTitle"]).strip(),
                published_at=datetime.fromtimestamp(row["announcementTime"] / 1000, tz=timezone.utc),
                url=PDF_BASE + row["adjunctUrl"] if row.get("adjunctUrl") else "",
                announcement_id=str(row["announcementId"]),
            )
        )
    return out


def search(
    keyword: str,
    start: date,
    end: date,
    *,
    page_size: int = 30,
    max_pages: int = 5,
    client: httpx.Client | None = None,
    pause: float = 1.0,
) -> list[Announcement]:
    own_client = client is None
    client = client or httpx.Client(timeout=20, headers={"User-Agent": "Mozilla/5.0 (mamatch buyer index)"})
    results: list[Announcement] = []
    try:
        for page in range(1, max_pages + 1):
            response = client.post(
                QUERY_URL,
                data={
                    "pageNum": page,
                    "pageSize": page_size,
                    "column": "szse",  # full A-share search despite the name
                    "tabName": "fulltext",
                    "searchkey": keyword,
                    "seDate": f"{start.isoformat()}~{end.isoformat()}",
                    "isHLtitle": "true",
                },
            )
            response.raise_for_status()
            batch = parse(response.json())
            results.extend(batch)
            if len(batch) < page_size:
                break
            time.sleep(pause)
    finally:
        if own_client:
            client.close()
    return results
