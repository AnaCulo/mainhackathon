"""Read the documented tenant policy and print its fingerprint for operator review."""

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.brane_client import policy_digest
from app.config import Settings


async def main():
    settings = Settings.load()
    if not settings.api_key:
        raise SystemExit("Set BRANE_API_KEY in .env.")
    async with httpx.AsyncClient(trust_env=False, timeout=settings.timeout) as http:
        try:
            response = await http.get(
                settings.base + "/policy",
                headers={
                    "Authorization": "Bearer " + settings.api_key,
                    "User-Agent": "hotline-intake/1.0",
                },
            )
            response.raise_for_status()
            policy = response.json()
            print("Policy SHA-256", policy_digest(policy))
            print(
                "Review the matching export in the team policy workbench before pinning."
            )
        except (httpx.HTTPError, ValueError):
            raise SystemExit("Could not read the team policy.") from None


if __name__ == "__main__":
    asyncio.run(main())
