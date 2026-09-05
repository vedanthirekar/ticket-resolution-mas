from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path

import pytest

pytestmark = pytest.mark.data_integrity

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BUSINESS_SPEC = REPOSITORY_ROOT / "synthetic_enterprise" / "business_spec"
POLICY_DIRECTORY = BUSINESS_SPEC / "policies"

POLICY_FILES = tuple(path for path in sorted(POLICY_DIRECTORY.glob("POL-*.md")) if path.is_file())


def _metadata(document: str) -> dict[str, str]:
    return {
        key.strip(): value.strip().strip("`")
        for key, value in re.findall(r"^\| ([^|]+) \| ([^|]+) \|$", document, re.MULTILINE)
    }


def _effective_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def test_company_catalog_has_reviewed_entity_counts_and_unique_references() -> None:
    company = (BUSINESS_SPEC / "COMPANY.md").read_text(encoding="utf-8")

    expected_counts = {"LOC": 3, "EMP": 15, "SVC": 25}
    for prefix, expected_count in expected_counts.items():
        references = re.findall(rf"^\| ({prefix}-[A-Z0-9]+) \|", company, re.MULTILINE)
        assert len(references) == expected_count
        assert len(set(references)) == expected_count


def test_every_policy_has_required_metadata_and_stable_unique_sections() -> None:
    assert POLICY_FILES, "No policy documents found"
    all_sections: list[str] = []

    for path in POLICY_FILES:
        document = path.read_text(encoding="utf-8")
        metadata = _metadata(document)

        assert {"Policy ID", "Version", "Effective from", "Effective through", "Scope"} <= (
            metadata.keys()
        )
        expected_stem = f"{metadata['Policy ID']}-v{metadata['Version']}"
        assert path.stem == expected_stem

        sections = re.findall(
            rf"^##+ ({re.escape(expected_stem)}#\d+(?:\.\d+)?)\b",
            document,
            re.MULTILINE,
        )
        assert sections, f"{path.name} has no stable section IDs"
        assert len(sections) == len(set(sections))
        all_sections.extend(sections)

    assert len(all_sections) == len(set(all_sections))


def test_policy_versions_have_contiguous_non_overlapping_effective_dates() -> None:
    versions_by_policy: defaultdict[str, list[tuple[int, date, date | None]]] = defaultdict(list)

    for path in POLICY_FILES:
        metadata = _metadata(path.read_text(encoding="utf-8"))
        end_value = metadata["Effective through"]
        versions_by_policy[metadata["Policy ID"]].append(
            (
                int(metadata["Version"]),
                _effective_date(metadata["Effective from"]),
                None if end_value == "Open-ended" else _effective_date(end_value),
            )
        )

    for versions in versions_by_policy.values():
        versions.sort()
        assert versions[-1][2] is None
        for current, following in pairwise(versions):
            current_version, _, current_end = current
            following_version, following_start, _ = following
            assert following_version == current_version + 1
            assert current_end is not None
            assert following_start == current_end + timedelta(days=1)


def test_decision_table_cites_existing_policy_sections() -> None:
    existing_sections: set[str] = set()
    for path in POLICY_FILES:
        existing_sections.update(
            re.findall(
                r"^##+ (POL-[A-Z]+-v\d+#\d+(?:\.\d+)?)\b",
                path.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        )

    decision_table = (BUSINESS_SPEC / "POLICY_DECISION_TABLE.md").read_text(encoding="utf-8")
    citations = re.findall(
        r"POL-([A-Z]+) v(\d+) §(\d+(?:\.\d+)?)(?:\u2013(\d+(?:\.\d+)?))?",
        decision_table,
    )
    assert citations, "Decision table contains no policy citations"

    for policy_suffix, version, first_section, last_section in citations:
        prefix = f"POL-{policy_suffix}-v{version}#"
        assert f"{prefix}{first_section}" in existing_sections
        if last_section:
            assert f"{prefix}{last_section}" in existing_sections
