from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
from typing import Any

import httpx


GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
NVIDIA_MODELS_URL = "https://integrate.api.nvidia.com/v1/models"


def _secret(env_name: str, prompt: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    return getpass.getpass(prompt).strip()


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return {"text": response.text[:500]}
    return payload if isinstance(payload, dict) else {"payload": payload}


def _error_summary(payload: dict[str, Any]) -> str:
    error = payload.get("error", payload)
    if isinstance(error, dict):
        return str(error.get("message", error.get("status", "request failed")))[:500]
    return str(error)[:500]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    gemini_key = _secret("GEMINI_API_KEY", "Gemini API key (hidden): ")
    nvidia_key = _secret("NVIDIA_API_KEY", "NVIDIA API key (hidden): ")
    if not gemini_key or not nvidia_key:
        raise SystemExit("both API keys are required")

    receipt: dict[str, Any] = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "credentials_persisted": False,
        "providers": {},
    }
    with httpx.Client(timeout=60.0) as client:
        gemini_response = client.get(
            GEMINI_MODELS_URL,
            headers={"x-goog-api-key": gemini_key},
            params={"pageSize": 1000},
        )
        gemini_payload = _safe_json(gemini_response)
        gemini_models = []
        if gemini_response.is_success:
            for model in gemini_payload.get("models", []):
                methods = model.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    gemini_models.append(str(model.get("name", "")).removeprefix("models/"))
        receipt["providers"]["gemini"] = {
            "http_status": gemini_response.status_code,
            "authenticated": gemini_response.is_success,
            "generate_content_models": sorted(name for name in gemini_models if name),
        }
        if not gemini_response.is_success:
            receipt["providers"]["gemini"]["error"] = _error_summary(gemini_payload)

        nvidia_response = client.get(
            NVIDIA_MODELS_URL,
            headers={"Authorization": f"Bearer {nvidia_key}"},
        )
        nvidia_payload = _safe_json(nvidia_response)
        nvidia_models = []
        if nvidia_response.is_success:
            nvidia_models = [
                str(model.get("id", ""))
                for model in nvidia_payload.get("data", [])
                if isinstance(model, dict) and model.get("id")
            ]
        receipt["providers"]["nvidia"] = {
            "http_status": nvidia_response.status_code,
            "authenticated": nvidia_response.is_success,
            "models": sorted(nvidia_models),
        }
        if not nvidia_response.is_success:
            receipt["providers"]["nvidia"]["error"] = _error_summary(nvidia_payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
