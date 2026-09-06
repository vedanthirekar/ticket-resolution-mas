from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, SecretStr, ValidationError

from luma.config import Settings

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ModelInvocation[OutputT: BaseModel]:
    value: OutputT
    input_tokens: int = 0
    output_tokens: int = 0


class StructuredModel(Protocol):
    provider: str
    model_name: str

    async def generate(
        self,
        *,
        stage: str,
        schema: type[OutputT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocation[OutputT]: ...


class LangChainStructuredModel:
    """Provider-neutral adapter around a LangChain chat model."""

    def __init__(
        self,
        model: BaseChatModel,
        *,
        provider: str,
        model_name: str,
        structured_output_method: Literal["function_calling", "json_mode", "json_schema"]
        | None = None,
        structured_output_max_attempts: int = 1,
    ) -> None:
        if structured_output_max_attempts < 1:
            raise ValueError("structured_output_max_attempts must be at least 1")
        self._model = model
        self.provider = provider
        self.model_name = model_name
        self._structured_output_method = structured_output_method
        self._structured_output_max_attempts = structured_output_max_attempts

    async def generate(
        self,
        *,
        stage: str,
        schema: type[OutputT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocation[OutputT]:
        structured_output_options: dict[str, Any] = {"include_raw": True}
        if self._structured_output_method is not None:
            structured_output_options["method"] = self._structured_output_method
        structured = self._model.with_structured_output(schema, **structured_output_options)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=json.dumps(payload, sort_keys=True, default=str)),
        ]
        response: Any = None
        for attempt in range(1, self._structured_output_max_attempts + 1):
            try:
                response = await structured.ainvoke(messages)
            except (OutputParserException, ValidationError) as caught_parsing_error:
                # Some LangChain/provider combinations raise parser failures directly
                # even with include_raw enabled. Normalize those failures so they get
                # the same bounded format-correction retry as returned parsing errors.
                response = {
                    "parsed": None,
                    "raw": None,
                    "parsing_error": caught_parsing_error,
                }
            if isinstance(response, dict) and response.get("parsed") is not None:
                break
            if attempt < self._structured_output_max_attempts:
                parsing_error = (
                    response.get("parsing_error") if isinstance(response, dict) else None
                )
                validation_feedback = (
                    str(parsing_error)[:1500]
                    if parsing_error is not None
                    else "The required schema function was not called."
                )
                messages.append(
                    SystemMessage(
                        content=(
                            f"FORMAT CORRECTION (attempt {attempt + 1}): Call the required "
                            f"{schema.__name__} schema function with corrected arguments. "
                            "Do not return prose. The previous response failed for this reason:\n"
                            f"{validation_feedback}"
                        )
                    )
                )
        if not isinstance(response, dict) or response.get("parsed") is None:
            parsing_error = response.get("parsing_error") if isinstance(response, dict) else None
            error_kind = (
                type(parsing_error).__name__ if parsing_error is not None else "missing_call"
            )
            error_detail = str(parsing_error)[:1500] if parsing_error is not None else ""
            raise ValueError(
                "model returned no valid structured output after "
                f"{self._structured_output_max_attempts} attempts ({error_kind}): {error_detail}"
            )
        parsed = response["parsed"]
        value = parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
        raw_message = response.get("raw")
        usage = getattr(raw_message, "usage_metadata", None) or {}
        return ModelInvocation(
            value=value,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )


class ScriptedStructuredModel:
    """Deterministic model double for graph, recovery, and safety tests."""

    provider = "scripted"
    model_name = "scripted-v1"

    def __init__(self, responses: dict[str, list[dict[str, Any]]]) -> None:
        self._responses: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
        for stage, values in responses.items():
            self._responses[stage].extend(values)
        self.calls: list[str] = []

    async def generate(
        self,
        *,
        stage: str,
        schema: type[OutputT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocation[OutputT]:
        del system_prompt, payload
        self.calls.append(stage)
        if not self._responses[stage]:
            raise RuntimeError(f"no scripted response for stage {stage}")
        return ModelInvocation(value=schema.model_validate(self._responses[stage].popleft()))


def build_model(settings: Settings) -> StructuredModel:
    """Build the configured live adapter without making an API call."""
    api_key = (
        settings.anthropic_api_key or settings.model_api_key
        if settings.model_provider == "anthropic"
        else settings.model_api_key
    )
    if api_key is None:
        expected_key = (
            "ANTHROPIC_API_KEY or LUMA_MODEL_API_KEY"
            if settings.model_provider == "anthropic"
            else "LUMA_MODEL_API_KEY"
        )
        raise ValueError(f"{expected_key} is required for live model execution")

    if settings.model_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model: BaseChatModel = ChatAnthropic(
            model_name=settings.model_name,
            api_key=SecretStr(api_key),
            max_tokens_to_sample=settings.model_max_output_tokens,
            max_retries=settings.model_max_retries,
            timeout=settings.model_timeout_seconds,
            stop=None,
        )
    elif settings.model_provider == "google_genai":
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = ChatGoogleGenerativeAI(
            model=settings.model_name,
            api_key=SecretStr(api_key),
            temperature=0,
            max_tokens=settings.model_max_output_tokens,
            max_retries=settings.model_max_retries,
            timeout=settings.model_timeout_seconds,
        )
    elif settings.model_provider == "openrouter":
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            model=settings.model_name,
            api_key=SecretStr(api_key),
            base_url=settings.openrouter_base_url,
            temperature=0,
            max_completion_tokens=settings.model_max_output_tokens,
            max_retries=settings.model_max_retries,
            timeout=settings.model_timeout_seconds,
            default_headers={"X-Title": "Luma Case Resolution"},
        )
    else:
        raise ValueError(f"unsupported model provider: {settings.model_provider}")
    return LangChainStructuredModel(
        model,
        provider=settings.model_provider,
        model_name=settings.model_name,
        # Anthropic supports native schema-constrained output. OpenRouter models do not
        # consistently honor JSON response formats, so use tool/function calling there.
        structured_output_method=(
            "json_schema"
            if settings.model_provider == "anthropic"
            else "function_calling"
            if settings.model_provider == "openrouter"
            else None
        ),
        structured_output_max_attempts=(
            settings.model_max_retries + 1
            if settings.model_provider in {"anthropic", "openrouter"}
            else 1
        ),
    )
