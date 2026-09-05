from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit one machine-readable event without logging prompts or customer text."""
    logger.info(
        json.dumps(
            {"timestamp": datetime.now(UTC).isoformat(), "event": event, **fields},
            sort_keys=True,
            default=str,
        )
    )
