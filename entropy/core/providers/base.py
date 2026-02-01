"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Callable


# Type for validation callbacks: takes response data, returns (is_valid, error_message)
ValidatorCallback = Callable[[dict], tuple[bool, str]]

# Type for retry notification callbacks: (attempt, max_retries, short_error_summary)
RetryCallback = Callable[[int, int, str], None]


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All providers must implement these methods with the same signatures
    to ensure drop-in compatibility.

    Args:
        api_key: API key or access token for the provider.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._cached_async_client = None

    async def close_async(self) -> None:
        """Close the cached async client to release connections cleanly.

        Must be called before the event loop shuts down to avoid
        'Event loop is closed' errors from orphaned httpx connections.
        """
        if self._cached_async_client is not None:
            await self._cached_async_client.close()
            self._cached_async_client = None

    @property
    @abstractmethod
    def default_simple_model(self) -> str:
        """Default model for simple_call (fast, cheap)."""
        ...

    @property
    @abstractmethod
    def default_reasoning_model(self) -> str:
        """Default model for reasoning_call (balanced)."""
        ...

    @property
    @abstractmethod
    def default_research_model(self) -> str:
        """Default model for agentic_research (with web search)."""
        ...

    @abstractmethod
    def simple_call(
        self,
        prompt: str,
        response_schema: dict,
        schema_name: str = "response",
        model: str | None = None,
        log: bool = True,
        max_tokens: int | None = None,
    ) -> dict:
        """Simple LLM call with structured output, no reasoning, no web search."""
        ...

    @abstractmethod
    async def simple_call_async(
        self,
        prompt: str,
        response_schema: dict,
        schema_name: str = "response",
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """Async version of simple_call for concurrent API requests."""
        ...

    def _retry_with_validation(
        self,
        call_fn,
        prompt: str,
        validator: ValidatorCallback | None,
        max_retries: int,
        on_retry: RetryCallback | None,
        extract_error_summary_fn,
        initial_prompt: str | None = None,
    ) -> dict:
        """Shared validation-retry loop for reasoning_call and agentic_research.

        Args:
            call_fn: Callable(effective_prompt) -> result_dict.
                     Called each attempt with the (possibly error-prepended) prompt.
            prompt: Base prompt text used as the suffix on validation retries.
            validator: Optional validator callback.
            max_retries: Max validation retries.
            on_retry: Optional retry notification callback.
            extract_error_summary_fn: Function to shorten error messages.
            initial_prompt: If provided, used for the first call instead of prompt.
                This allows previous_errors to be included on the first attempt
                without persisting them across validation retries.

        Returns:
            Validated result dict (or last attempt if retries exhausted).
        """
        effective_prompt = initial_prompt if initial_prompt is not None else prompt
        attempts = 0
        last_error_summary = ""
        result = {}

        while attempts <= max_retries:
            result = call_fn(effective_prompt)

            if validator is None:
                return result

            is_valid, error_msg = validator(result)
            if is_valid:
                return result

            attempts += 1
            last_error_summary = extract_error_summary_fn(error_msg)

            if attempts <= max_retries:
                if on_retry:
                    on_retry(attempts, max_retries, last_error_summary)
                effective_prompt = f"{error_msg}\n\n---\n\n{prompt}"

        if on_retry:
            on_retry(max_retries + 1, max_retries, f"EXHAUSTED: {last_error_summary}")
        return result

    @abstractmethod
    def reasoning_call(
        self,
        prompt: str,
        response_schema: dict,
        schema_name: str = "response",
        model: str | None = None,
        reasoning_effort: str = "low",
        log: bool = True,
        previous_errors: str | None = None,
        validator: ValidatorCallback | None = None,
        max_retries: int = 2,
        on_retry: RetryCallback | None = None,
    ) -> dict:
        """LLM call with reasoning and structured output, but NO web search."""
        ...

    @abstractmethod
    def agentic_research(
        self,
        prompt: str,
        response_schema: dict,
        schema_name: str = "research_data",
        model: str | None = None,
        reasoning_effort: str = "low",
        log: bool = True,
        previous_errors: str | None = None,
        validator: ValidatorCallback | None = None,
        max_retries: int = 2,
        on_retry: RetryCallback | None = None,
    ) -> tuple[dict, list[str]]:
        """Perform agentic research with web search and structured output."""
        ...
