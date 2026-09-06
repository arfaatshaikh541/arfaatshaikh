"""Headless CLI client.

There is no native Windows shell in this build (this environment cannot
build or run one — see core/RUNBOOK.md). This CLI is the real, working
interface for now: `aura chat` streams real incremental output to your
terminal, `aura status` reports genuine capability state.
"""
from __future__ import annotations

import asyncio
import sys

import click

from .actions import build_default_registry
from .config import load_settings
from .memory import MemoryStore
from .providers import ModelRouter, NoProviderAvailable, OllamaProvider
from .status import CapabilityStatus, registry


def _build_runtime():
    settings = load_settings()
    memory = MemoryStore(settings.database_url)
    registry.set("memory.store", CapabilityStatus.LIVE, f"connected to {settings.database_url}")
    actions = build_default_registry(memory)
    ollama = OllamaProvider(host=settings.ollama_host, model=settings.ollama_model)
    router = ModelRouter(primary=ollama, allow_test_fallback=settings.allow_test_provider)
    return memory, actions, router


@click.group()
def main() -> None:
    """AURA headless core CLI."""


@main.command()
def status() -> None:
    """Print real capability status (health-checks the model provider)."""
    _, _, router = _build_runtime()

    async def _check() -> None:
        try:
            await router.select_provider()
        except NoProviderAvailable:
            pass  # status registry already recorded the honest reason

    asyncio.run(_check())
    for name, info in registry.snapshot().items():
        click.echo(f"{name:30s} {info['status']:18s} {info['detail']}")


@main.command()
def chat() -> None:
    """Interactive chat loop with real streaming output."""
    _memory, actions, router = _build_runtime()

    async def _loop() -> None:
        click.echo("AURA core chat. Type 'exit' to quit.")
        while True:
            try:
                text = input("you> ").strip()
            except EOFError:
                break
            if text.lower() in {"exit", "quit"}:
                break
            if not text:
                continue

            action_result = actions.dispatch(text)
            if action_result is not None:
                click.echo(f"aura [{action_result.status.value}]> {action_result.message}")
                continue

            sys.stdout.write("aura> ")
            sys.stdout.flush()
            try:
                async for chunk in router.generate_stream(text, history=[]):
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
            except NoProviderAvailable as exc:
                sys.stdout.write(f"\n[unavailable] {exc}")
            sys.stdout.write("\n")

    asyncio.run(_loop())


if __name__ == "__main__":
    main()
