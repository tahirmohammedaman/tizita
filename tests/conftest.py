import copy
import json
from pathlib import Path

import pytest

from tizita.cache import Artifact, Manifest
from tizita.dag import build_units, manifest_path_for, resolve_upstream, unit_key
from tizita.util import Project, sha256_bytes

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def good_sb() -> dict:
    return json.loads((FIXTURES / "storyboard_good.json").read_text(encoding="utf-8"))


@pytest.fixture
def project(tmp_path, good_sb) -> Project:
    (tmp_path / "storyboard.json").write_text(json.dumps(good_sb, ensure_ascii=False))
    (tmp_path / "ethics").mkdir()
    (tmp_path / "ethics" / "consents.yaml").write_text("[]\n")
    return Project(tmp_path)


def materialize(sb: dict, project: Project, provider: dict | None = None) -> Manifest:
    """Pretend a full run happened: write a fake artifact for every unit and record it."""
    manifest = Manifest(project.manifest)
    fresh: set[str] = set()
    for unit in build_units(sb, project):
        shas, stale = resolve_upstream(unit, manifest, fresh)
        assert not stale, (unit.id, stale)
        prov = provider if unit.capability else None
        key = unit_key(unit, shas, prov)
        path = manifest_path_for(project, unit, key, "bin")
        data = f"{unit.id}:{key}".encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        cands = None
        if unit.stage in ("references", "music"):
            cands = [Artifact(project.rel(path), sha256_bytes(data + bytes([i]))) for i in range(4)]
        manifest.record(
            stage=unit.stage,
            unit=unit.unit,
            key=key,
            stage_version=1,
            artifact=Artifact(project.rel(path), sha256_bytes(data)),
            provider=prov,
            seed=unit.seed,
            fields=unit.fields,
            upstream=shas,
            candidates=cands,
        )
        fresh.add(unit.id)
    manifest.save()
    return manifest


@pytest.fixture
def mutate(good_sb):
    def _m(fn):
        sb = copy.deepcopy(good_sb)
        fn(sb)
        return sb

    return _m
