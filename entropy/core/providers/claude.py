"""Claude (Anthropic) LLM Provider implementation."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic

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
    log_file = logs_dir / f"{timestamp}_claude_{function_name}.json"

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
        "provider": "claude",
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


def _extract_json_from_text(text: str) -> dict | None:
    """Try to extract JSON from text, handling code blocks."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in code block
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    if "```" in text:
        start = text.find("```") + 3
        # Skip language identifier if present
        newline = text.find("\n", start)
        if newline > start:
            start = newline + 1
        end = text.find("```", start)
        if end > start:
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    return None


class ClaudeProvider(LLMProvider):
    """Claude (Anthropic) LLM provider.

    Supports both API key (sk-ant-...) and OAuth access token authentication.
    """

    def __init__(self, api_key: str = "") -> None:
        if not api_key:
            raise ValueError(
                "Anthropic credentials not found. Set one of:\n"
                "  export ANTHROPIC_API_KEY=sk-ant-...       # API key\n"
                "  export ANTHROPIC_ACCESS_TOKEN=...         # OAuth token\n"
                "Get your key from: https://console.anthropic.com/settings/keys"
            )
        super().__init__(api_key)

    @property
    def default_simple_model(self) -> str:
        return "claude-haiku-4-5-20251001"

    @property
    def default_reasoning_model(self) -> str:
        return "claude-sonnet-4-5-20250929"

    @property
    def default_research_model(self) -> str:
        return "claude-sonnet-4-5-20250929"

    def _is_oauth_token(self) -> bool:
        """Check if the credential is an OAuth access token (not an API key)."""
        return not self._api_key.startswith("sk-ant-")

    def _get_client(self) -> anthropic.Anthropic:
        if self._is_oauth_token():
            return anthropic.Anthropic(
                auth_token=self._api_key,
            )
        return anthropic.Anthropic(api_key=self._api_key)

    def _get_async_client(self) -> anthropic.AsyncAnthropic:
        if self._is_oauth_token():
            return anthropic.AsyncAnthropic(
                auth_token=self._api_key,
            )
        return anthropic.AsyncAnthropic(api_key=self._api_key)

    def _build_json_prompt(self, prompt: str, response_schema: dict) -> str:
        """Add JSON schema instruction to prompt."""
        return (
            f"{prompt}\n\n"
            f"Respond with valid JSON matching this schema:\n"
            f"```json\n{json.dumps(response_schema, indent=2)}\n```\n"
            f"Return ONLY the JSON object, no other text."
        )

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

        full_prompt = self._build_json_prompt(prompt, response_schema)

        logger.info(
            f"[Claude] simple_call starting - model={model}, schema={schema_name}"
        )

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens or 4096,
            messages=[{"role": "user", "content": full_prompt}],
        )

        # Extract structured data from text response
        structured_data = None
        for block in response.content:
            if block.type == "text":
                structured_data = _extract_json_from_text(block.text)
                if structured_data:
                    break

        if log:
            _log_request_response(
                function_name="simple_call",
                request={"model": model, "prompt_length": len(full_prompt)},
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

        full_prompt = self._build_json_prompt(prompt, response_schema)

        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens or 4096,
            messages=[{"role": "user", "content": full_prompt}],
        )

        # Extract structured data from text response
        structured_data = None
        for block in response.content:
            if block.type == "text":
                structured_data = _extract_json_from_text(block.text)
                if structured_data:
                    break

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
        """Claude reasoning call - uses the same model but with more detailed prompting."""
        model = model or self.default_reasoning_model
        client = self._get_client()

        # Prepend previous errors if provided
        effective_prompt = prompt
        if previous_errors:
            effective_prompt = f"{previous_errors}\n\n---\n\n{prompt}"

        attempts = 0
        last_error_summary = ""

        while attempts <= max_retries:
            full_prompt = self._build_json_prompt(effective_prompt, response_schema)

            response = client.messages.create(
                model=model,
                max_tokens=8192,
                messages=[{"role": "user", "content": full_prompt}],
            )

            # Extract structured data
            structured_data = None
            for block in response.content:
                if block.type == "text":
                    structured_data = _extract_json_from_text(block.text)
                    if structured_data:
                        break

            if log:
                _log_request_response(
                    function_name="reasoning_call",
                    request={"model": model, "prompt_length": len(full_prompt)},
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
        """Claude agentic research with web search."""
        model = model or self.default_research_model
        client = self._get_client()

        effective_prompt = prompt
        if previous_errors:
            effective_prompt = f"{previous_errors}\n\n---\n\n{prompt}"

        attempts = 0
        last_error_summary = ""
        all_sources: list[str] = []

        while attempts <= max_retries:
            # Add JSON schema instruction
            full_prompt = (
                f"{effective_prompt}\n\n"
                f"Respond with valid JSON matching this schema:\n"
                f"```json\n{json.dumps(response_schema, indent=2)}\n```"
            )

            logger.info(f"[Claude] agentic_research - model={model}")

            response = client.messages.create(
                model=model,
                max_tokens=8192,
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 5,
                    }
                ],
                messages=[{"role": "user", "content": full_prompt}],
            )

            # Extract structured data and sources from response
            structured_data = None
            sources: list[str] = []

            for block in response.content:
                # Check for web search results
                if block.type == "web_search_tool_result":
                    if hasattr(block, "content") and block.content:
                        for result in block.content:
                            if hasattr(result, "url"):
                                sources.append(result.url)

                # Check for text with possible citations
                if block.type == "text":
                    text = block.text

                    # Try to extract JSON if we haven't yet
                    if structured_data is None:
                        structured_data = _extract_json_from_text(text)

                    # Extract citation URLs if present
                    if hasattr(block, "citations") and block.citations:
                        for citation in block.citations:
                            if hasattr(citation, "url"):
                                sources.append(citation.url)

            all_sources.extend(sources)

            logger.info(f"[Claude] Web search completed, found {len(sources)} sources")

            if log:
                _log_request_response(
                    function_name="agentic_research",
                    request={"model": model, "prompt_length": len(full_prompt)},
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
