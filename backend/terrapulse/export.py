"""Write every API response to static JSON so the dashboard can be hosted
without a server (same payloads, same paths as the live API).

Run:  uv run python -m terrapulse.export
"""

from __future__ import annotations

import json
from pathlib import Path

from . import analysis as an, data
from .api import catalog, provenance
from .catalog import REGIONS, VARIABLES

OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def main() -> None:
    _write(OUT / "catalog.json", catalog())
    _write(OUT / "provenance.json", provenance())
    for variable in VARIABLES:
        if not data.available(variable):
            # Never export a variable without real data behind it; remove stale files.
            (OUT / "overview" / f"{variable}.json").unlink(missing_ok=True)
            for region in REGIONS:
                (OUT / "analysis" / region / f"{variable}.json").unlink(missing_ok=True)
            print("skipped", variable, "-", data.unavailable_reason(variable))
            continue
        _write(OUT / "overview" / f"{variable}.json", an.overview(variable))
        for region in REGIONS:
            _write(OUT / "analysis" / region / f"{variable}.json", an.analysis(region, variable))
            print("exported", region, variable)


if __name__ == "__main__":
    main()
