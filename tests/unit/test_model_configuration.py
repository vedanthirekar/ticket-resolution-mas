from typing import Any, cast

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from luma.agents.contracts import CaseCategory, InvestigationPlanOutput
from luma.agents.models import LangChainStructuredModel, build_model
from luma.config import Settings


class _StructuredRunnable:
    def __init__(self, *, failures_before_success: int = 0) -> None:
        self.failures_before_success = failures_before_success
        self.calls = 0

    async def ainvoke(self, messages: list[Any]) -> dict[str, Any]:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            return {
                "parsed": None,
                "raw": None,
                "parsing_error": ValueError("next_call must be present when incomplete"),
            }
        if self.failures_before_success:
            correction = messages[-1]
            assert "FORMAT CORRECTION" in str(correction.content)
            assert "next_call must be present" in str(correction.content)
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
    def __init__(self, *, failures_before_success: int = 0) -> None:
        self.options: dict[str, Any] = {}
        self.runnable = _StructuredRunnable(failures_before_success=failures_before_success)

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
