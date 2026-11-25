"""`previous_take`: reuse the unit's last cached artifact when every live provider failed, so a
re-run never leaves the film without audio. The stage passes the path in `inputs.previous_path`."""

from __future__ import annotations

from pathlib import Path

from tizita.providers.base import Provider, Request, Result
from tizita.providers.errors import Unavailable


class PreviousTake(Provider):
    executor = "local"

    def call(self, req: Request) -> Result:
        raw = req.inputs.get("previous_path")
        path = Path(raw) if raw else None
        if path is None or not path.is_file():
            raise Unavailable("no previous take cached for this unit")
        data = path.read_bytes()
        return Result(
            model="previous-take",
            data=data,
            mime="audio/wav",
            ext=path.suffix.lstrip(".") or "wav",
            metrics={"reused": str(path)},
        )
