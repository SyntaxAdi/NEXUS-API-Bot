import httpx
import logging
import json
from modules.config import NEXUS_API_URLS, NEXUS_API_KEY, PASTEBIN_URL

logger = logging.getLogger("api_client")

async def check_api_status() -> tuple[bool, str]:
    """Returns (is_ready, message). Checks all backend URLs to ensure cluster is ready."""
    try:
        async with httpx.AsyncClient() as client:
            for url in NEXUS_API_URLS:
                try:
                    res = await client.get(
                        f"{url}/status",
                        headers={"x-api-key": NEXUS_API_KEY},
                        timeout=5.0
                    )
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("state") != "done":
                            return False, f"Node {url} is not ready. State: {data.get('state')}"
                    else:
                        return False, f"Node {url} returned HTTP {res.status_code}"
                except Exception as e:
                    return False, f"Node {url} is unreachable: {e}"
        return True, "All API nodes are ready."
    except Exception as e:
        logger.error(f"Cluster Check Error: {e}")
        return False, "Cluster is currently unreachable."

async def fetch_search_results(query: str, limit: int = 10) -> list[str]:
    """Streams the ripgrep results from all backend nodes."""
    results = []
    try:
        async with httpx.AsyncClient() as client:
            for url in NEXUS_API_URLS:
                try:
                    async with client.stream(
                        "GET", 
                        f"{url}/search",
                        params={"search": query, "limit": limit},
                        headers={"x-api-key": NEXUS_API_KEY},
                        timeout=30.0
                    ) as response:
                        if response.status_code != 200:
                            results.append(f"Error from {url}: HTTP {response.status_code}")
                            continue
                        
                        async for chunk in response.aiter_lines():
                            text = chunk.strip()
                            if text:
                                if text.startswith('{"error":'):
                                    try:
                                        err = json.loads(text)
                                        results.append(f"Backend Error: {err['error']}")
                                        continue
                                    except:
                                        pass
                                results.append(text)
                except Exception as node_err:
                    results.append(f"Failed to reach {url}: {node_err}")
        return results
    except Exception as e:
        logger.error(f"API Search Error: {e}")
        return [f"Error during search: {str(e)}"]

async def create_paste(content: str) -> str:
    """Uploads large search results to PatBin as a burn-after-reading paste."""
    pastebin_url = PASTEBIN_URL
    payload = {
        "title": "Nexus API Results",
        "content": content,
        "language": "plaintext",
        "is_public": True,
        "burn_after_read": True
    }
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{pastebin_url}/api/paste",
                json=payload,
                timeout=15.0
            )
            if res.status_code == 201:
                data = res.json()
                return f"{pastebin_url}/{data['id']}"
            else:
                return ""
    except Exception as e:
        logger.error(f"PasteBin Error: {e}")
        return ""
    return ""