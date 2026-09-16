from __future__ import annotations

import asyncio
import json
import re
from time import monotonic
from typing import Any

import httpx

import run_hosted_mcp_llm_evaluation as base


_LOCK = asyncio.Lock()
_LAST_REQUEST_AT: dict[str, float] = {}
_MIN_INTERVAL_SECONDS = {
    "integrate.api.nvidia.com": 4.0,
    "generativelanguage.googleapis.com": 15.0,
}


async def _pace(url: str) -> None:
    host = httpx.URL(url).host
    minimum = _MIN_INTERVAL_SECONDS.get(host, 0.0)
    async with _LOCK:
        elapsed = monotonic() - _LAST_REQUEST_AT.get(host, 0.0)
        if elapsed < minimum:
            await asyncio.sleep(minimum - elapsed)
        _LAST_REQUEST_AT[host] = monotonic()


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after", "")
    try:
        return min(max(float(retry_after), 1.0), 30.0)
    except ValueError:
        pass
    match = re.search(r"retry in\s+([0-9.]+)s", response.text, flags=re.IGNORECASE)
    if match:
        return min(max(float(match.group(1)), 1.0), 30.0)
    return min(4.0 * attempt, 30.0)


async def _paced_post_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    attempts: int,
) -> httpx.Response:
    for attempt in range(1, attempts + 1):
        await _pace(url)
        try:
            response = await client.post(url, headers=headers, json=payload)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if attempt == attempts:
                raise RuntimeError(f"provider transport failure: {type(exc).__name__}") from exc
            delay = min(4.0 * attempt, 30.0)
            print(
                json.dumps(
                    {
                        "provider_retry": attempt,
                        "reason": type(exc).__name__,
                        "wait_seconds": delay,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            await asyncio.sleep(delay)
            continue
        if response.is_success:
            return response
        retryable = response.status_code == 429 or response.status_code >= 500
        if not retryable or attempt == attempts:
            raise RuntimeError(
                f"provider HTTP {response.status_code}: {base._error_message(response)}"
            )
        delay = _retry_delay(response, attempt)
        print(
            json.dumps(
                {
                    "provider_retry": attempt,
                    "status": response.status_code,
                    "wait_seconds": delay,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")


base._post_with_retries = _paced_post_with_retries


if __name__ == "__main__":
    base.main()
