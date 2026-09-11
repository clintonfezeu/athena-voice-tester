"""Command-line entry point.

    python -m bot.cli list-scenarios
    python -m bot.cli call --scenario simple_scheduling_new_patient
    python -m bot.cli run-batch
    python -m bot.cli run-batch --scenario simple_scheduling_new_patient --scenario medication_refill_request
"""

from __future__ import annotations

import json
import logging

import click

from bot.config import get_settings
from bot.orchestrator import result_to_dict, results_summary, run_batch, run_call
from bot.personas import ScenarioError, get_scenario, load_all_scenarios

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@click.group()
def cli() -> None:
    """athena-voice-tester: automated patient-simulator calls against the Athena test line."""


@cli.command("list-scenarios")
def list_scenarios() -> None:
    """Print every available test scenario."""
    for scenario in load_all_scenarios():
        click.echo(f"{scenario.id:<40} [{scenario.category}] {scenario.title}")


@cli.command("call")
@click.option("--scenario", "scenario_id", required=True, help="Scenario id, see list-scenarios.")
@click.option("--json", "as_json", is_flag=True, help="Print the result as JSON.")
def call_command(scenario_id: str, as_json: bool) -> None:
    """Place a single call for one scenario and wait for it to finish."""
    settings = get_settings()
    try:
        scenario = get_scenario(scenario_id)
    except ScenarioError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Calling {settings.target_number} for scenario '{scenario_id}'...")
    result = run_call(scenario, settings=settings)

    if as_json:
        click.echo(json.dumps(result_to_dict(result), indent=2))
    else:
        click.echo(results_summary([result]))

    if not result.ok:
        raise SystemExit(1)


@cli.command("run-batch")
@click.option(
    "--scenario",
    "scenario_ids",
    multiple=True,
    help="Limit the batch to these scenario ids (repeatable). Default: all scenarios.",
)
@click.option("--delay", "delay_seconds", type=int, default=None, help="Override the pacing delay between calls.")
def run_batch_command(scenario_ids: tuple[str, ...], delay_seconds: int | None) -> None:
    """Run every scenario (or a chosen subset), one call at a time."""
    settings = get_settings()
    all_scenarios = load_all_scenarios()

    if scenario_ids:
        by_id = {s.id: s for s in all_scenarios}
        missing = [sid for sid in scenario_ids if sid not in by_id]
        if missing:
            raise click.ClickException(f"Unknown scenario id(s): {', '.join(missing)}")
        scenarios = [by_id[sid] for sid in scenario_ids]
    else:
        scenarios = all_scenarios

    click.echo(f"Running {len(scenarios)} call(s) against {settings.target_number}...")
    results = run_batch(scenarios, settings=settings, delay_seconds=delay_seconds)
    click.echo(results_summary(results))

    if any(not r.ok for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
