from __future__ import annotations

from click.testing import CliRunner

from aura_core.cli import main


def test_model_embed_returns_a_real_vector():
    runner = CliRunner()

    result = runner.invoke(main, ["model", "embed", "hello world"])

    assert result.exit_code == 0, result.output
    assert "8-dimensional vector" in result.output
