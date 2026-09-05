from __future__ import annotations

import argparse
import json

from luma.config import get_settings
from luma.db.session import Database
from luma.runtime import run_async
from luma_enterprise.generator import generate_dataset


async def _run(write_manifests: bool, *, allow_runtime_data: bool) -> None:
    settings = get_settings()
    database = Database(settings.database_url, echo=settings.database_echo)
    try:
        manifest, _ = await generate_dataset(
            database,
            write_manifests=write_manifests,
            allow_runtime_data=allow_runtime_data,
        )
        print(json.dumps(manifest["validation_summary"], indent=2, sort_keys=True))
        print(f"dataset_fingerprint={manifest['dataset_fingerprint']}")
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and validate Luma business data")
    parser.add_argument(
        "--no-write-manifests", action="store_true", help="validate without updating files"
    )
    parser.add_argument(
        "--force-with-runtime-data",
        action="store_true",
        help="allow replacement when application cases exist (isolated reset only)",
    )
    arguments = parser.parse_args()
    run_async(
        _run(
            write_manifests=not arguments.no_write_manifests,
            allow_runtime_data=arguments.force_with_runtime_data,
        )
    )


if __name__ == "__main__":
    main()
