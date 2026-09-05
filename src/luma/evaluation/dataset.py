from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from luma.evaluation.contracts import EvalCase, EvalDataset

DEFAULT_DATASET_PATH = Path("evals/datasets/luma_cases_v1.json")


def load_dataset(path: Path = DEFAULT_DATASET_PATH) -> EvalDataset:
    raw = json.loads(path.read_text(encoding="utf-8"))
    templates = raw.pop("scenario_templates")
    cases: list[EvalCase] = []
    for template in templates:
        shared = {key: value for key, value in template.items() if key != "variations"}
        for index, variation in enumerate(template["variations"], start=1):
            payload: dict[str, Any] = {
                **shared,
                **variation,
                "case_id": f"{template['scenario_id']}-{index:02d}",
            }
            cases.append(EvalCase.model_validate(payload))
    return EvalDataset.model_validate({**raw, "cases": cases})
