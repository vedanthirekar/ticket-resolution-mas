from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DATASET_VERSION = "luma_business_v1"
GENERATOR_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    dataset_version: str = DATASET_VERSION
    generator_version: str = GENERATOR_VERSION
    seed: int = 20260903
    reference_time: datetime = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    customer_count: int = 300
    membership_count: int = 150
    appointment_count: int = 2000
    background_payment_count: int = 1490
    manifest_path: Path = Path("data_generation/manifests/luma_business_v1.json")
    incident_manifest_path: Path = Path(
        "data_generation/private_manifests/luma_business_v1_incidents.json"
    )
