from __future__ import annotations

import uvicorn

from luma.runtime import run_async


def main() -> None:
    config = uvicorn.Config("luma.api.app:app", host="127.0.0.1", port=8000, reload=False)
    run_async(uvicorn.Server(config).serve())


if __name__ == "__main__":
    main()
