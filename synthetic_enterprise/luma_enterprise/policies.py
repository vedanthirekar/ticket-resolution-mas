from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from luma_enterprise.identifiers import deterministic_id

POLICY_AREA = {
    "POL-ADJ": "adjustments",
    "POL-BOOK": "booking",
    "POL-CAN": "cancellation",
    "POL-MEM": "membership",
    "POL-PAY": "payments",
}


@dataclass(frozen=True, slots=True)
class PolicyRows:
    documents: list[dict[str, Any]]
    versions: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    links: list[dict[str, Any]]


def _checksum(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _metadata(document: str) -> dict[str, str]:
    return {
        key.strip(): value.strip().strip("`")
        for key, value in re.findall(r"^\| ([^|]+) \| ([^|]+) \|$", document, re.MULTILINE)
    }


def _date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _sections(*, dataset_version: str, version_id: UUID, document: str) -> list[dict[str, Any]]:
    headings = list(
        re.finditer(
            r"^(#{2,6}) (POL-[A-Z]+-v\d+#\d+(?:\.\d+)?)\s+(.+)$",
            document,
            re.MULTILINE,
        )
    )
    rows: list[dict[str, Any]] = []
    parents_by_level: dict[int, UUID] = {}

    for index, match in enumerate(headings):
        level = len(match.group(1))
        section_id = match.group(2)
        heading = match.group(3).strip()
        body_start = match.end()
        body_end = headings[index + 1].start() if index + 1 < len(headings) else len(document)
        body = document[body_start:body_end].strip()
        row_id = deterministic_id(dataset_version, "policy_section", section_id)
        parent_candidates = [candidate for candidate in parents_by_level if candidate < level]
        parent_id = parents_by_level[max(parent_candidates)] if parent_candidates else None
        rows.append(
            {
                "id": row_id,
                "policy_version_id": version_id,
                "section_id": section_id,
                "parent_section_id": parent_id,
                "heading": heading,
                "body": body,
                "sort_order": index,
                "content_checksum": _checksum(f"{heading}\n{body}"),
            }
        )
        parents_by_level[level] = row_id
        for deeper_level in tuple(
            existing_level for existing_level in parents_by_level if existing_level > level
        ):
            del parents_by_level[deeper_level]

    return rows


def build_policy_rows(
    *, dataset_version: str, policy_directory: Path, generated_at: datetime
) -> PolicyRows:
    files = sorted(policy_directory.glob("POL-*.md"))
    parsed: list[tuple[Path, str, dict[str, str]]] = []
    for path in files:
        document = path.read_text(encoding="utf-8")
        parsed.append((path, document, _metadata(document)))

    versions_by_policy: dict[str, list[int]] = {}
    for _, _, metadata in parsed:
        versions_by_policy.setdefault(metadata["Policy ID"], []).append(int(metadata["Version"]))

    documents: list[dict[str, Any]] = []
    seen_documents: set[str] = set()
    versions: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []

    version_ids: dict[tuple[str, int], UUID] = {}
    for policy_id, policy_versions in versions_by_policy.items():
        for version in policy_versions:
            version_ids[(policy_id, version)] = deterministic_id(
                dataset_version, "policy_version", f"{policy_id}-v{version}"
            )

    for path, document, metadata in parsed:
        policy_id = metadata["Policy ID"]
        version = int(metadata["Version"])
        document_id = deterministic_id(dataset_version, "policy_document", policy_id)
        if policy_id not in seen_documents:
            title_match = re.search(r"^# (.+)$", document, re.MULTILINE)
            if title_match is None:
                raise ValueError(f"Policy {path} has no title")
            documents.append(
                {
                    "id": document_id,
                    "policy_id": policy_id,
                    "title": title_match.group(1),
                    "policy_area": POLICY_AREA[policy_id],
                    "created_at": generated_at,
                    "updated_at": generated_at,
                }
            )
            seen_documents.add(policy_id)

        effective_through_value = metadata["Effective through"]
        version_id = version_ids[(policy_id, version)]
        highest_version = max(versions_by_policy[policy_id])
        versions.append(
            {
                "id": version_id,
                "policy_document_id": document_id,
                "version": version,
                "effective_from": _date(metadata["Effective from"]),
                "effective_through": (
                    None
                    if effective_through_value == "Open-ended"
                    else _date(effective_through_value)
                ),
                "status": "active" if version == highest_version else "superseded",
                "scope": {"description": metadata["Scope"]},
                "supersedes_version_id": version_ids.get((policy_id, version - 1)),
                "source_path": f"synthetic_enterprise/business_spec/policies/{path.name}",
                "content_checksum": _checksum(document),
                "published_at": datetime.combine(
                    _date(metadata["Effective from"]), datetime.min.time(), tzinfo=UTC
                ),
                "created_at": generated_at,
                "updated_at": generated_at,
            }
        )
        sections.extend(
            _sections(dataset_version=dataset_version, version_id=version_id, document=document)
        )

    section_ids = {row["section_id"]: row["id"] for row in sections}
    links: list[dict[str, Any]] = []

    for section_id, source_id in section_ids.items():
        match = re.fullmatch(r"(POL-[A-Z]+)-v(\d+)#(.+)", section_id)
        if match is None or int(match.group(2)) <= 1:
            continue
        previous = f"{match.group(1)}-v{int(match.group(2)) - 1}#{match.group(3)}"
        if previous in section_ids:
            link_reference = f"{section_id}:supersedes:{previous}"
            links.append(
                {
                    "id": deterministic_id(dataset_version, "policy_link", link_reference),
                    "source_section_id": source_id,
                    "target_section_id": section_ids[previous],
                    "link_type": "supersedes",
                }
            )

    explicit_links = (
        ("POL-CAN-v2#5.1", "POL-CAN-v2#3.2", "exception_to"),
        ("POL-CAN-v2#5.1", "POL-CAN-v2#3.3", "exception_to"),
        ("POL-MEM-v2#5.1", "POL-CAN-v2#4.1", "references"),
        ("POL-MEM-v2#5.2", "POL-CAN-v2#3.2", "references"),
    )
    for source, target, link_type in explicit_links:
        link_reference = f"{source}:{link_type}:{target}"
        links.append(
            {
                "id": deterministic_id(dataset_version, "policy_link", link_reference),
                "source_section_id": section_ids[source],
                "target_section_id": section_ids[target],
                "link_type": link_type,
            }
        )

    return PolicyRows(documents, versions, sections, links)
