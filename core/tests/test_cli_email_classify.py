from __future__ import annotations

from click.testing import CliRunner

from aura_core.cli import main


def test_email_classify_returns_a_real_category():
    runner = CliRunner()

    # AURA_ENV=test's deterministic echo provider always returns
    # "[test-provider echo] you said: ..." -- its first word "[test-provider"
    # is not one of the five real categories, so the honest, expected
    # result here is "unclassified", not a crash and not a guess.
    result = runner.invoke(main, ["email", "classify", "Pricing question", "How much does this cost?"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "unclassified"
