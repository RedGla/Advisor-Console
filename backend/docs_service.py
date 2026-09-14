"""Fetch and cache the advisor's Google Docs prompt and grounding content."""

import asyncio
import json
import os
import time
from typing import Any

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

GOOGLE_DOCS_SCOPE = "https://www.googleapis.com/auth/documents.readonly"
SYSTEM_PROMPT_DOCUMENT_ID = os.getenv(
    "GOOGLE_SYSTEM_PROMPT_DOCUMENT_ID",
    os.getenv("GOOGLE_DOCS_PROMPT_ID", "1ujFrCT7jG7PzeVcQIsunTXUDa9keuamYY-55k_lkl4"),
)
GROUNDING_DOCUMENT_ID = os.getenv(
    "GOOGLE_GROUNDING_DOCUMENT_ID",
    os.getenv("GOOGLE_DOCS_GROUNDING_ID", "17rH7oJj3XwwVGZMk_T5JnK-efpiKB-Vi1Z-yXf_y3Lk"),
)
CACHE_TTL_SECONDS = int(os.getenv("GOOGLE_DOCS_CACHE_TTL_SECONDS", "300"))

_cache: dict[str, tuple[float, str]] = {}
_cache_lock = asyncio.Lock()


class DocsServiceError(Exception):
    """Raised when Google Docs credentials or document retrieval fails."""


def _credentials() -> Any:
    credentials_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    try:
        if credentials_json:
            info = json.loads(credentials_json)
            if "private_key" in info:
                info["private_key"] = info["private_key"].replace("\\n", "\n")
            return service_account.Credentials.from_service_account_info(
                info, scopes=[GOOGLE_DOCS_SCOPE]
            )
        if credentials_file:
            return service_account.Credentials.from_service_account_file(
                credentials_file, scopes=[GOOGLE_DOCS_SCOPE]
            )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise DocsServiceError("Invalid Google service-account credentials") from error

    raise DocsServiceError(
        "Google Docs credentials are not configured; set "
        "GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS"
    )


def extract_text_from_doc(document: dict[str, Any]) -> str:
    parts: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            text_run = value.get("textRun")
            if isinstance(text_run, dict) and text_run.get("content"):
                parts.append(text_run["content"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document.get("body", {}).get("content", []))
    return "".join(parts).strip()


def _extract_text(document: dict[str, Any]) -> str:
    return extract_text_from_doc(document)


def _fetch_document(document_id: str) -> str:
    try:
        service = build("docs", "v1", credentials=_credentials(), cache_discovery=False)
        document = service.documents().get(documentId=document_id).execute()
        content = _extract_text(document)
    except DocsServiceError:
        raise
    except Exception as error:
        raise DocsServiceError(f"Unable to fetch Google Doc {document_id}") from error

    if not content:
        raise DocsServiceError(f"Google Doc {document_id} is empty")
    return content


async def _get_document(document_id: str, cache_key: str) -> str:
    now = time.monotonic()
    async with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

    try:
        content = await asyncio.to_thread(_fetch_document, document_id)
    except DocsServiceError:
        if cached:
            return cached[1]
        raise

    async with _cache_lock:
        _cache[cache_key] = (time.monotonic(), content)
    return content


async def get_system_prompt() -> str:
    return await _get_document(SYSTEM_PROMPT_DOCUMENT_ID, "system_prompt")


async def get_grounding_document() -> str:
    return await _get_document(GROUNDING_DOCUMENT_ID, "grounding_document")


async def get_advisor_context() -> dict[str, str]:
    system_prompt, grounding_document = await asyncio.gather(
        get_system_prompt(), get_grounding_document()
    )
    return {
        "system_prompt": system_prompt,
        "grounding_document": grounding_document,
    }