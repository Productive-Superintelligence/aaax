from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aaax import Strategy, create_strategy_app, load_strategy
from aaax.cli import main


def test_strategy_app_runs_and_invokes_resources():
    strategy = Strategy("analyst-system", description="Fixture system.")
    strategy.channel(
        "events",
        ref="psi://society/source-channels/channels/finance_ticks",
    )
    strategy.tactic(
        "finance_baseline",
        ref="psi://society/analyst-tactics/tactics/finance_baseline",
        handler=lambda input_value, context=None: {
            "handled": input_value,
            "context": context or {},
        },
    )

    @strategy.runner
    def run(input_value, *, context=None):
        return {
            "input": input_value,
            "resource_count": len(strategy.resources),
            "context": context or {},
        }

    client = TestClient(create_strategy_app(strategy))

    assert client.get("/health").json() == {
        "ok": True,
        "strategy": "analyst-system",
    }
    assert client.get("/resources").json()[0]["kind"] == "channel"
    run_response = client.post(
        "/run",
        json={"input": {"task": "summarize"}, "context": {"request": "demo"}},
    )
    invoke_response = client.post(
        "/resources/finance_baseline/invoke",
        json={"input": {"records": []}},
    )

    assert run_response.status_code == 200
    assert run_response.json()["output"]["resource_count"] == 2
    assert invoke_response.status_code == 200
    assert invoke_response.json()["output"] == {
        "handled": {"records": []},
        "context": {},
    }


def test_strategy_loader_from_directory(tmp_path: Path):
    strategy_file = tmp_path / "strategy.py"
    strategy_file.write_text(
        """
from aaax import Strategy


def build_strategy():
    strategy = Strategy("loaded")
    strategy.service("api", ref="psi://demo/app/services/api")
    return strategy
""".lstrip(),
        encoding="utf-8",
    )

    strategy = load_strategy(tmp_path)

    assert strategy.name == "loaded"
    assert strategy.resources[0].kind == "service"


def test_cli_inspect_prints_strategy(tmp_path: Path, capsys):
    strategy_file = tmp_path / "strategy.py"
    strategy_file.write_text(
        """
from aaax import Strategy

strategy = Strategy("cli-demo")
strategy.tactic("review", ref="psi://demo/pkg/tactics/review")
""".lstrip(),
        encoding="utf-8",
    )

    assert main(["inspect", str(strategy_file)]) == 0
    out = capsys.readouterr().out

    assert "cli-demo" in out
    assert "tactic review psi://demo/pkg/tactics/review" in out


def test_default_runner_exposes_strategy_pack():
    strategy = Strategy("empty")
    strategy.package("analysts", ref="psi://society/analyst-tactics")

    client = TestClient(create_strategy_app(strategy))
    response = client.post("/run", json={"input": {"ok": True}})

    assert response.status_code == 200
    assert response.json()["output"]["strategy"] == "empty"
    assert response.json()["output"]["resources"][0]["kind"] == "package"
