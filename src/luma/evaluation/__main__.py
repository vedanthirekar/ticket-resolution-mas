from __future__ import annotations

import argparse
import logging
from pathlib import Path

from luma.agents.models import build_model
from luma.config import get_settings
from luma.db.session import Database
from luma.evaluation.dataset import DEFAULT_DATASET_PATH, load_dataset
from luma.evaluation.runner import run_live_evaluation, write_report
from luma.retrieval.embeddings import HashingEmbeddingProvider
from luma.runtime import run_async


async def _run(args: argparse.Namespace) -> None:
    dataset = load_dataset(args.dataset)
    selected = [case for case in dataset.cases if args.split == "all" or case.split == args.split]
    if args.offset:
        selected = selected[args.offset :]
    if args.limit is not None:
        selected = selected[: args.limit]
    if not args.live:
        print(
            f"Validated {len(dataset.cases)} cases in {dataset.dataset_version}; "
            f"selected {len(selected)} ({args.split}). Use --live to invoke the configured model."
        )
        return

    settings = get_settings()
    database = Database(settings.database_url, echo=settings.database_echo)
    try:
        report = await run_live_evaluation(
            dataset=dataset,
            selected_cases=selected,
            database=database,
            model=build_model(settings),
            embedding_provider=HashingEmbeddingProvider(),
            settings=settings,
        )
        output = args.output or Path("evals/reports/generated") / f"{report.experiment_id}.json"
        write_report(report, output)
        print(f"Wrote {report.summary['case_count']} evaluated cases to {output}")
        print(f"Overall strict pass rate: {report.summary['overall_pass_rate']}")
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or run the Luma evaluation dataset")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--split", choices=("all", "development", "held_out"), default="all")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--live", action="store_true", help="invoke the configured model (may cost money)"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_async(_run(args))


if __name__ == "__main__":
    main()
