import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Load credentials from environment
THREADS_USER_ID = os.getenv("THREADS_USER_ID")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")

class ThreadsPublisher:
    def __init__(self):
        self.user_id = THREADS_USER_ID
        self.access_token = THREADS_ACCESS_TOKEN
        self.enabled = bool(self.user_id and self.access_token)
        if not self.enabled:
            logger.warning("THREADS_USER_ID or THREADS_ACCESS_TOKEN missing. Threads publisher is running in dry-run mode.")

    async def publish_post(self, text: str, image_url: Optional[str] = None) -> bool:
        """Publishes a text post (with optional image URL) to Threads via Graph API"""
        if not self.enabled:
            logger.info(f"[DRY-RUN] Publishing to Threads:\nText:\n{text}\nImage: {image_url}")
            return True

        async with httpx.AsyncClient() as client:
            try:
                # 1. Create a Threads Media Container
                # For Threads, we must first request a container ID
                container_url = f"https://graph.threads.net/v1.0/{self.user_id}/media"
                
                params = {
                    "access_token": self.access_token,
                    "text": text
                }
                
                if image_url:
                    params["media_type"] = "IMAGE"
                    params["image_url"] = image_url
                else:
                    params["media_type"] = "TEXT"

                logger.info("Creating Threads media container...")
                resp = await client.post(container_url, params=params, timeout=15)
                
                if resp.status_code != 200:
                    logger.error(f"Failed to create Threads container. Status: {resp.status_code}, Body: {resp.text}")
                    return False
                    
                container_id = resp.json().get("id")
                if not container_id:
                    logger.error("No container ID returned in Threads API response")
                    return False

                # 2. Publish the created container
                publish_url = f"https://graph.threads.net/v1.0/{self.user_id}/media_publish"
                publish_params = {
                    "access_token": self.access_token,
                    "creation_id": container_id
                }
                
                logger.info(f"Publishing Threads container {container_id}...")
                pub_resp = await client.post(publish_url, params=publish_params, timeout=15)
                
                if pub_resp.status_code == 200:
                    logger.info("Successfully published post to Threads")
                    return True
                else:
                    logger.error(f"Failed to publish Threads container. Status: {pub_resp.status_code}, Body: {pub_resp.text}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error publishing to Threads Graph API: {e}")
                return False
