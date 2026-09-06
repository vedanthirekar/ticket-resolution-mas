import json
from typing import Any, cast

import pytest
from anthropic import transform_schema
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from luma.agents.contracts import (
    CaseCategory,
    InvestigationDecisionOutput,
    InvestigationPlanOutput,
)
from luma.agents.models import LangChainStructuredModel, build_model
from luma.config import Settings


class _StructuredRunnable:
    def __init__(
        self, *, failures_before_success: int = 0, raise_parser_failure: bool = False
    ) -> None:
        self.failures_before_success = failures_before_success
        self.raise_parser_failure = raise_parser_failure
        self.calls = 0

    async def ainvoke(self, messages: list[Any]) -> dict[str, Any]:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            if self.raise_parser_failure:
                raise OutputParserException(
                    "Unknown tool type: 'get_customer'. "
                    "Available tools: InvestigationDecisionOutput"
                )
            return {
                "parsed": None,
                "raw": None,
                "parsing_error": ValueError("next_call must be present when incomplete"),
            }
        if self.failures_before_success:
            correction = messages[-1]
            assert "FORMAT CORRECTION" in str(correction.content)
            expected_error = (
                "Unknown tool type" if self.raise_parser_failure else "next_call must be present"
            )
            assert expected_error in str(correction.content)
        return {
            "parsed": InvestigationPlanOutput(
                category=CaseCategory.CANCELLATION_FEE_DISPUTE,
                material_event_date="2026-08-20",
                required_evidence_types=["customer"],
                investigation_objectives=["Establish customer identity"],
                policy_query="provider cancellation fee",
                rationale="The complaint disputes a cancellation fee.",
            ),
            "raw": None,
        }


class _RecordingChatModel:
    def __init__(
        self, *, failures_before_success: int = 0, raise_parser_failure: bool = False
    ) -> None:
        self.options: dict[str, Any] = {}
        self.runnable = _StructuredRunnable(
            failures_before_success=failures_before_success,
            raise_parser_failure=raise_parser_failure,
        )

    def with_structured_output(self, schema: type[Any], **options: Any) -> _StructuredRunnable:
        del schema
        self.options = options
        return self.runnable


def test_openrouter_requires_free_model_suffix() -> None:
    with pytest.raises(ValidationError, match=":free"):
        Settings(
            _env_file=None,
            model_provider="openrouter",
            model_name="minimax/minimax-m3",
        )


def test_openrouter_adapter_builds_without_calling_provider() -> None:
    settings = Settings(
        _env_file=None,
        model_provider="openrouter",
        model_name="minimax/minimax-m3:free",
        model_api_key="test-not-a-real-key",
    )
    model = build_model(settings)
    assert isinstance(model, LangChainStructuredModel)
    assert model.provider == "openrouter"
    assert model.model_name.endswith(":free")


def test_anthropic_adapter_uses_standard_environment_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    settings = Settings(
        _env_file=None,
        model_provider="anthropic",
        model_name="claude-sonnet-4-6",
    )

    model = build_model(settings)

    assert isinstance(model, LangChainStructuredModel)
    assert model.provider == "anthropic"
    assert model.model_name == "claude-sonnet-4-6"


@pytest.mark.parametrize(
    "schema",
    [
        transform_schema(InvestigationDecisionOutput),
        convert_to_openai_tool(InvestigationDecisionOutput)["function"]["parameters"],
    ],
    ids=["anthropic-json-schema", "openrouter-function-calling"],
)
def test_provider_schema_preserves_exact_tool_arguments(schema: dict[str, Any]) -> None:
    serialized = json.dumps(schema)

    assert '"appointment_reference"' in serialized
    assert '"booking_attempt_reference"' in serialized
    assert '"membership_reference"' in serialized
    assert '"as_of"' in serialized


@pytest.mark.asyncio
async def test_openrouter_adapter_enforces_function_calling_structured_output() -> None:
    chat_model = _RecordingChatModel()
    model = LangChainStructuredModel(
        cast(BaseChatModel, chat_model),
        provider="openrouter",
        model_name="minimax/minimax-m3:free",
        structured_output_method="function_calling",
    )

    result = await model.generate(
        stage="case_manager_plan",
        schema=InvestigationPlanOutput,
        system_prompt="Return a plan.",
        payload={"complaint": "I was charged after my provider cancelled."},
    )

    assert result.value.category is CaseCategory.CANCELLATION_FEE_DISPUTE
    assert chat_model.options == {"include_raw": True, "method": "function_calling"}


@pytest.mark.asyncio
async def test_adapter_retries_missing_structured_call_with_format_correction() -> None:
    chat_model = _RecordingChatModel(failures_before_success=1)
    model = LangChainStructuredModel(
        cast(BaseChatModel, chat_model),
        provider="openrouter",
        model_name="minimax/minimax-m3:free",
        structured_output_method="function_calling",
        structured_output_max_attempts=2,
    )

    result = await model.generate(
        stage="investigation_decision",
        schema=InvestigationPlanOutput,
        system_prompt="Return a plan.",
        payload={"complaint": "I was charged after my provider cancelled."},
    )

    assert result.value.category is CaseCategory.CANCELLATION_FEE_DISPUTE
    assert chat_model.runnable.calls == 2


@pytest.mark.asyncio
async def test_adapter_retries_raised_output_parser_exception() -> None:
    chat_model = _RecordingChatModel(failures_before_success=1, raise_parser_failure=True)
    model = LangChainStructuredModel(
        cast(BaseChatModel, chat_model),
        provider="openrouter",
        model_name="minimax/minimax-m3:free",
        structured_output_method="function_calling",
        structured_output_max_attempts=2,
    )

    result = await model.generate(
        stage="investigation_decision",
        schema=InvestigationPlanOutput,
        system_prompt="Return a plan.",
        payload={"complaint": "The booking site showed a technical error."},
    )

    assert result.value.category is CaseCategory.CANCELLATION_FEE_DISPUTE
    assert chat_model.runnable.calls == 2
