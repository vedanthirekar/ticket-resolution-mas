from __future__ import annotations

from uuid import UUID, uuid5

NAMESPACE = UUID("ff529a8d-fdf9-53a8-b015-fda78a4af166")


def deterministic_id(dataset_version: str, entity: str, reference: str) -> UUID:
    return uuid5(NAMESPACE, f"{dataset_version}:{entity}:{reference}")
