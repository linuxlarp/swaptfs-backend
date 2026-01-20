import os

import aiofiles
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import LOGS as logger


router = APIRouter(prefix="/images", tags=["Images"])
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "images", "cache", "cities")
os.makedirs(CACHE_DIR, exist_ok=True)

@router.get("/{city}")
async def get_city_image(city: str):
    """
    Fetch and cache a representative city image from Unsplash.

    Normalizes the city name, checks for a cached image on disk, and if absent
    queries the Unsplash API, saves the first result to a cache directory, and
    serves it as a file response.

    Args:
        city (str): The city name used as the Unsplash search query and cache key.

    Returns:
        FileResponse: A JPEG image file for the requested city.

    Raises:
        HTTPException:
            - 404: No image found for the given city.
            - 500: Error while requesting or saving the image.

    Logs:
        - Requests for city images, cache hits, downloads, and errors.
    """

    city = city.strip().lower()
    cache_path = os.path.join(CACHE_DIR, f"{city}.jpg")

    logger.info(f"GET /images/{city}")

    if os.path.exists(cache_path):
        logger.info(f"Using cached Unsplash image for city {city}")
        return FileResponse(cache_path)

    url = (
        f"https://api.unsplash.com/search/photos?"
        f"query={city}&orientation=landscape&per_page=1&order_by=popular&client_id={UNSPLASH_KEY}"
    )

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            res = await client.get(url)
            data = res.json()
            if not data.get("results"):
                raise HTTPException(status_code=404, detail="No image found for that city.")

            image_url = data["results"][0]["urls"]["full"]
            image_res = await client.get(image_url)

            async with aiofiles.open(cache_path, "wb") as f:
                await f.write(image_res.content)

            logger.info(f"Saved Unsplash image for {city}")
            return FileResponse(cache_path)
        except Exception as e:
            logger.error(f"Unsplash image fetch error: {e}")
            raise HTTPException(status_code=500, detail="Failed to load image.")
