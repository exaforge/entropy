"""OpenAI LLM Provider implementation."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI, AsyncOpenAI

from .base import LLMProvider, ValidatorCallback, RetryCallback


logger = logging.getLogger(__name__)


def _get_logs_dir() -> Path:
    """Get logs directory, create if needed."""
    logs_dir = Path("./logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _log_request_response(
    function_name: str,
    request: dict,
    response: Any,
    sources: list[str] | None = None,
) -> None:
    """Log full request and response to a JSON file."""
    logs_dir = _get_logs_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"{timestamp}_{function_name}.json"

    # Convert response to dict if possible
    response_dict = None
    if hasattr(response, "model_dump"):
        try:
            response_dict = response.model_dump(mode="json", warnings=False)
        except Exception:
            response_dict = str(response)
    elif hasattr(response, "__dict__"):
        response_dict = str(response)
    else:
        response_dict = str(response)

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "function": function_name,
        "request": request,
        "response": response_dict,
        "sources_extracted": sources or [],
    }

    with open(log_file, "w") as f:
        json.dump(log_data, f, indent=2, default=str)


def _extract_error_summary(error_msg: str) -> str:
    """Extract a concise error summary from validation error message."""
    if not error_msg:
        return "validation error"

    lines = error_msg.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            if "ERROR in" in line:
                return line[:60]
            elif "Problem:" in line:
                return line.replace("Problem:", "").strip()[:60]
            elif line:
                return line[:60]

    return "validation error"


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider using the Responses API."""

    def __init__(self, api_key: str = "") -> None:
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Set it as an environment variable.\n"
                "  export OPENAI_API_KEY=sk-..."
            )
        super().__init__(api_key)

    @property
    def default_simple_model(self) -> str:
        return "gpt-5-mini"

    @property
    def default_reasoning_model(self) -> str:
        return "gpt-5"

    @property
    def default_research_model(self) -> str:
        return "gpt-5"

    def _get_client(self) -> OpenAI:
        return OpenAI(api_key=self._api_key)

    def _get_async_client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self._api_key)

    def simple_call(
        self,
        prompt: str,
        response_schema: dict,
        schema_name: str = "response",
        model: str | None = None,
        log: bool = True,
        max_tokens: int | None = None,
    ) -> dict:
        model = model or self.default_simple_model
        client = self._get_client()

        request_params = {
            "model": model,
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": response_schema,
                }
            },
        }

        if max_tokens is not None:
            request_params["max_output_tokens"] = max_tokens

        logger.info(f"[LLM] simple_call starting - model={model}, schema={schema_name}")
        logger.info(f"[LLM] prompt length: {len(prompt)} chars")

        api_start = time.time()
        response = client.responses.create(**request_params)
        api_elapsed = time.time() - api_start

        logger.info(f"[LLM] API response received in {api_elapsed:.2f}s")

        # Extract structured data
        structured_data = None
        for item in response.output:
            if hasattr(item, "type") and item.type == "message":
                for content_item in item.content:
                    if (
                        hasattr(content_item, "type")
                        and content_item.type == "output_text"
                    ):
                        if hasattr(content_item, "text"):
                            structured_data = json.loads(content_item.text)

        if log:
            _log_request_response(
                function_name="simple_call",
                request=request_params,
                response=response,
            )

        return structured_data or {}

    async def simple_call_async(
        self,
        prompt: str,
        response_schema: dict,
        schema_name: str = "response",
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        model = model or self.default_simple_model
        client = self._get_async_client()

        request_params = {
            "model": model,
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": response_schema,
                }
            },
        }

        if max_tokens is not None:
            request_params["max_output_tokens"] = max_tokens

        response = await client.responses.create(**request_params)

        # Extract structured data
        structured_data = None
        for item in response.output:
            if hasattr(item, "type") and item.type == "message":
                for content_item in item.content:
                    if (
                        hasattr(content_item, "type")
                        and content_item.type == "output_text"
                    ):
                        if hasattr(content_item, "text"):
                            structured_data = json.loads(content_item.text)

        return structured_data or {}

    def reasoning_call(
        self,
        prompt: str,
        response_schema: dict,
        schema_name: str = "response",
        model: str | None = None,
        log: bool = True,
        previous_errors: str | None = None,
        validator: ValidatorCallback | None = None,
        max_retries: int = 2,
        on_retry: RetryCallback | None = None,
    ) -> dict:
        model = model or self.default_reasoning_model
        client = self._get_client()

        # Prepend previous errors if provided
        effective_prompt = prompt
        if previous_errors:
            effective_prompt = f"{previous_errors}\n\n---\n\n{prompt}"

        attempts = 0
        last_error_summary = ""

        while attempts <= max_retries:
            request_params = {
                "model": model,
                "reasoning": {"effort": "low"},
                "input": [{"role": "user", "content": effective_prompt}],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": response_schema,
                    }
                },
            }

            response = client.responses.create(**request_params)

            # Extract structured data
            structured_data = None
            for item in response.output:
                if hasattr(item, "type") and item.type == "message":
                    for content_item in item.content:
                        if (
                            hasattr(content_item, "type")
                            and content_item.type == "output_text"
                        ):
                            if hasattr(content_item, "text"):
                                structured_data = json.loads(content_item.text)

            if log:
                _log_request_response(
                    function_name="reasoning_call",
                    request=request_params,
                    response=response,
                )

            result = structured_data or {}

            if validator is None:
                return result

            is_valid, error_msg = validator(result)
            if is_valid:
                return result

            attempts += 1
            last_error_summary = _extract_error_summary(error_msg)

            if attempts <= max_retries:
                if on_retry:
                    on_retry(attempts, max_retries, last_error_summary)
                effective_prompt = f"{error_msg}\n\n---\n\n{prompt}"

        if on_retry:
            on_retry(max_retries + 1, max_retries, f"EXHAUSTED: {last_error_summary}")
        return result

    def agentic_research(
        self,
        prompt: str,
        response_schema: dict,
        schema_name: str = "research_data",
        model: str | None = None,
        log: bool = True,
        previous_errors: str | None = None,
        validator: ValidatorCallback | None = None,
        max_retries: int = 2,
        on_retry: RetryCallback | None = None,
    ) -> tuple[dict, list[str]]:
        model = model or self.default_research_model
        client = self._get_client()

        effective_prompt = prompt
        if previous_errors:
            effective_prompt = f"{previous_errors}\n\n---\n\n{prompt}"

        attempts = 0
        last_error_summary = ""
        all_sources: list[str] = []

        while attempts <= max_retries:
            request_params = {
                "model": model,
                "input": effective_prompt,
                "tools": [{"type": "web_search"}],
                "reasoning": {"effort": "low"},
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": response_schema,
                    }
                },
                "include": ["web_search_call.action.sources"],
            }

            response = client.responses.create(**request_params)

            # Extract structured data and sources
            structured_data = None
            sources: list[str] = []

            for item in response.output:
                if hasattr(item, "type") and item.type == "web_search_call":
                    if hasattr(item, "action") and item.action:
                        if hasattr(item.action, "sources") and item.action.sources:
                            for source in item.action.sources:
                                if isinstance(source, dict):
                                    if "url" in source:
                                        sources.append(source["url"])
                                elif hasattr(source, "url"):
                                    sources.append(source.url)

                if hasattr(item, "type") and item.type == "message":
                    for content_item in item.content:
                        if (
                            hasattr(content_item, "type")
                            and content_item.type == "output_text"
                        ):
                            if hasattr(content_item, "text"):
                                structured_data = json.loads(content_item.text)
                            if (
                                hasattr(content_item, "annotations")
                                and content_item.annotations
                            ):
                                for annotation in content_item.annotations:
                                    if (
                                        hasattr(annotation, "type")
                                        and annotation.type == "url_citation"
                                    ):
                                        if hasattr(annotation, "url"):
                                            sources.append(annotation.url)

            all_sources.extend(sources)

            if log:
                _log_request_response(
                    function_name="agentic_research",
                    request=request_params,
                    response=response,
                    sources=list(set(sources)),
                )

            result = structured_data or {}

            if validator is None:
                return result, list(set(all_sources))

            is_valid, error_msg = validator(result)
            if is_valid:
                return result, list(set(all_sources))

            attempts += 1
            last_error_summary = _extract_error_summary(error_msg)

            if attempts <= max_retries:
                if on_retry:
                    on_retry(attempts, max_retries, last_error_summary)
                effective_prompt = f"{error_msg}\n\n---\n\n{prompt}"

        if on_retry:
            on_retry(max_retries + 1, max_retries, f"EXHAUSTED: {last_error_summary}")
        return result, list(set(all_sources))
