from __future__ import annotations

from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from seas.cli import app
from seas.experiments.verify import verify_scenario

runner = CliRunner()


def test_run_and_verify_correctness_scenario(tmp_path: Path) -> None:
    out = tmp_path / "res"
    r = runner.invoke(
        app, ["run", "configs/scenarios/S6.yaml", "--out", str(out), "--workers", "1", "--seeds", "1000,1001"]
    )
    assert r.exit_code == 0, r.output
    df = pd.read_csv(out / "S6" / "runs.csv")
    assert len(df) == 12
    assert (df.eligibility_violations == 0).all()
    assert df.filter(like="reason_NO_ELIGIBLE_NODE").sum().sum() > 0  # TEE_GPU and 160 GB jobs rejected
    assert verify_scenario(out / "S6") == []
    r = runner.invoke(app, ["verify", str(out)])
    assert r.exit_code == 0, r.output


def test_confirmatory_seed_override_refused(tmp_path: Path) -> None:
    r = runner.invoke(app, ["run", "configs/scenarios/S1.yaml", "--out", str(tmp_path), "--seeds", "1000"])
    assert r.exit_code != 0
