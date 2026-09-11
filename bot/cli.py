"""Command-line entry point.

    python -m bot.cli list-scenarios
    python -m bot.cli call --scenario simple_scheduling_new_patient
    python -m bot.cli run-batch
    python -m bot.cli run-batch --scenario simple_scheduling_new_patient --scenario medication_refill_request
    python -m bot.cli analyze-all
    python -m bot.cli build-report
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click

from bot.bug_analyzer import analyze_and_save, write_bug_report
from bot.config import get_settings
from bot.orchestrator import CALLS_DIR, result_to_dict, results_summary, run_batch, run_call
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


@cli.command("analyze-all")
@click.option("--force", is_flag=True, help="Re-analyze calls that already have findings.json.")
def analyze_all_command(force: bool) -> None:
    """Run the bug analyzer over every saved call that has a transcript."""
    settings = get_settings()

    if not CALLS_DIR.is_dir():
        click.echo(f"No calls found under {CALLS_DIR}/")
        return

    analyzed = 0
    for call_dir in sorted(CALLS_DIR.iterdir()):
        transcript_path = call_dir / "transcript.json"
        findings_path = call_dir / "findings.json"
        if not transcript_path.exists():
            continue
        if findings_path.exists() and not force:
            continue

        metadata_path = call_dir / "metadata.json"
        scenario_id = None
        if metadata_path.exists():
            scenario_id = json.loads(metadata_path.read_text(encoding="utf-8")).get("scenario_id")
        if not scenario_id:
            scenario_id = json.loads(transcript_path.read_text(encoding="utf-8")).get("scenario_id")

        try:
            scenario = get_scenario(scenario_id)
        except ScenarioError:
            click.echo(f"  skip {call_dir.name}: unknown scenario_id={scenario_id!r}")
            continue

        click.echo(f"  analyzing {call_dir.name} ({scenario_id})...")
        analyze_and_save(call_dir, scenario, settings=settings)
        analyzed += 1

    click.echo(f"Analyzed {analyzed} call(s).")


@cli.command("build-report")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=Path("reports/BUG_REPORT.md"))
def build_report_command(out_path: Path) -> None:
    """Regenerate reports/BUG_REPORT.md from every data/calls/*/findings.json."""
    path = write_bug_report(out_path=out_path, calls_dir=CALLS_DIR)
    click.echo(f"Wrote {path}")


if __name__ == "__main__":
    cli()
