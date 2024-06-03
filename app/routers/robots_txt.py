from datetime import timedelta

from aiohttp import ClientSession
from fastapi import APIRouter, Response

from .. import persistence
from ..config import DARK_VISITORS_ACCESS_TOKEN, HOST

router = APIRouter()
ROBOTS_TXT_CACHE_KEY = HOST + "robots.txt"


@router.get("/robots.txt", include_in_schema=False)
async def robots_txt(response: Response):
    """Robots blocklist."""
    directives = await get_blocklist()
    return Response(directives, headers={"Content-Type": "text/plain"})


async def get_blocklist() -> str:
    """Retrieve the Robots.txt block list contents"""
    content = await persistence.get(ROBOTS_TXT_CACHE_KEY)

    if content is None:
        async with ClientSession() as session:
            response = await session.post(
                "https://api.darkvisitors.com/robots-txts",
                headers={"Authorization": f"Bearer {DARK_VISITORS_ACCESS_TOKEN}"},
                data={
                    "agent_types": [
                        "AI Assistant",
                        "AI Data Scraper",
                        "AI Search Crawler",
                        "Archivers",
                        "Intelligence Gatherers",
                        "Scrapers",
                        "Search Engine Crawlers",
                        "SEO Crawlers",
                        "Undocumented AI Agent",
                    ],
                    "disallow": "/",
                },
            )
            if not response.ok:
                return ""

            content = await response.read()
            await persistence.set(
                ROBOTS_TXT_CACHE_KEY, content, expire=timedelta(days=1)
            )

    return content
