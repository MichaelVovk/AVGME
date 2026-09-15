from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import click
import cv2

from .adb import Adb, AdbError
from .bot import Bot
from .config import load_config
from .runner import build_tasks, run_forever, run_once
from .tasks import REGISTRY
from .vision import load_templates

TEMPLATE_DIR = Path("templates")
CAPTURE_DIR = Path("captures")
DEBUG_DIR = Path("debug")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)-18s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def _adb_from(config: dict) -> Adb:
    section = config.get("adb", {})
    return Adb(host=section.get("host", "127.0.0.1"), port=int(section.get("port", 5555)))


def _make_bot(config: dict, *, dry_run: bool) -> Bot:
    adb = _adb_from(config)
    adb.connect()
    threshold = config.get("vision", {}).get("default_threshold", 0.87)
    templates = load_templates(TEMPLATE_DIR, threshold)
    return Bot(adb, templates, config, dry_run=dry_run, debug_dir=DEBUG_DIR)


config_option = click.option(
    "--config", "config_path", type=click.Path(path_type=Path), default=None,
    help="Path to tasks.yaml (default: config/tasks.yaml).",
)
verbose_option = click.option("-v", "--verbose", is_flag=True, help="Debug logging.")


@click.group()
def main() -> None:
    """AVGME - Last Asylum: Plague automation.

    Start with `avgme doctor`, then `avgme capture` to collect screenshots,
    `avgme crop` to cut templates out of them, and `avgme run --dry-run` to
    check the bot is aiming at the right buttons before it taps anything.
    """


@main.command()
@config_option
@verbose_option
def doctor(config_path: Path | None, verbose: bool) -> None:
    """Check adb, the emulator connection, resolution and templates."""
    _setup_logging(verbose)
    problems: list[str] = []

    try:
        config = load_config(config_path)
    except FileNotFoundError as exc:
        click.secho(f"FAIL  config: {exc}", fg="red")
        sys.exit(1)
    click.secho("ok    config loaded", fg="green")

    try:
        Adb.executable()
        click.secho("ok    adb found on PATH", fg="green")
    except AdbError as exc:
        click.secho(f"FAIL  {exc}", fg="red")
        sys.exit(1)

    adb = _adb_from(config)
    try:
        adb.connect()
        click.secho(f"ok    connected to {adb.serial}", fg="green")
    except AdbError as exc:
        click.secho(f"FAIL  {exc}", fg="red")
        sys.exit(1)

    expected = config.get("adb", {}).get("expect_resolution")
    try:
        width, height = adb.resolution()
    except AdbError as exc:
        click.secho(f"FAIL  resolution: {exc}", fg="red")
        sys.exit(1)

    if expected and [width, height] != list(expected):
        click.secho(
            f"FAIL  resolution is {width}x{height}, config expects "
            f"{expected[0]}x{expected[1]}. Templates are matched 1:1, so every "
            "one of them will miss. Set the emulator back, or recapture.",
            fg="red",
        )
        problems.append("resolution")
    else:
        click.secho(f"ok    resolution {width}x{height}", fg="green")

    threshold = config.get("vision", {}).get("default_threshold", 0.87)
    templates = load_templates(TEMPLATE_DIR, threshold)
    if not templates:
        click.secho(
            f"FAIL  no templates in {TEMPLATE_DIR}/. Run `avgme capture` then "
            "`avgme crop` - see the README.",
            fg="red",
        )
        problems.append("templates")
    else:
        click.secho(f"ok    {len(templates)} templates loaded", fg="green")
        for group, label in (
            ("home/anchor", "home anchor (required - proves we're on the base screen)"),
            ("home/collect", "collect badges (required by the collect task)"),
            ("common/close", "popup close buttons (required for recovery)"),
        ):
            if not any(key.startswith(group) for key in templates):
                click.secho(f"WARN  no {group}* template: {label}", fg="yellow")
                problems.append(group)

    try:
        adb.screencap()
        click.secho("ok    screencap decodes", fg="green")
    except AdbError as exc:
        click.secho(f"FAIL  screencap: {exc}", fg="red")
        problems.append("screencap")

    if problems:
        click.secho(f"\n{len(problems)} problem(s) to fix before running live.", fg="yellow")
        sys.exit(1)
    click.secho("\nAll checks passed.", fg="green", bold=True)


@main.command()
@config_option
@verbose_option
@click.option("--name", default="screen", help="Filename prefix for the capture.")
@click.option("--count", default=1, show_default=True, help="How many frames to grab.")
@click.option("--delay", default=3.0, show_default=True, help="Seconds between frames.")
def capture(
    config_path: Path | None, verbose: bool, name: str, count: int, delay: float
) -> None:
    """Save screenshots from the emulator into captures/.

    This is step one. Templates have to be cut from your own screen at your own
    resolution - line the game up on the screen you want (home with badges
    showing, the scavenge menu, a popup) and grab it.
    """
    _setup_logging(verbose)
    config = load_config(config_path)
    adb = _adb_from(config)
    adb.connect()

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        if index:
            click.echo(f"waiting {delay}s...")
            time.sleep(delay)
        frame = adb.screencap()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = CAPTURE_DIR / f"{name}-{stamp}-{index:02d}.png"
        cv2.imwrite(str(path), frame)
        height, width = frame.shape[:2]
        click.secho(f"saved {path} ({width}x{height})", fg="green")


@main.command()
@click.argument("screenshot", type=click.Path(exists=True, path_type=Path))
@click.argument("template_name")
def crop(screenshot: Path, template_name: str) -> None:
    """Cut a template out of a screenshot.

    TEMPLATE_NAME is a path under templates/, e.g. `home/anchor_base` or
    `scavenge/claim`. A window opens: drag a box around the button, press ENTER
    to save or C to cancel.

    Crop tight. Include the button's distinctive artwork and as little
    background as possible - background is what changes between screens.
    """
    image = cv2.imread(str(screenshot), cv2.IMREAD_COLOR)
    if image is None:
        raise click.ClickException(f"could not read {screenshot}")

    click.echo("Drag a box around the element, then press ENTER. Press C to cancel.")
    x, y, w, h = cv2.selectROI("crop template", image, showCrosshair=False)
    cv2.destroyAllWindows()

    if w == 0 or h == 0:
        raise click.ClickException("nothing selected")

    out = TEMPLATE_DIR / f"{template_name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), image[y : y + h, x : x + w])
    click.secho(f"saved {out} ({w}x{h})", fg="green")


@main.command("list-templates")
@config_option
def list_templates(config_path: Path | None) -> None:
    """Show which templates are loaded and what they're keyed as."""
    config = load_config(config_path)
    threshold = config.get("vision", {}).get("default_threshold", 0.87)
    templates = load_templates(TEMPLATE_DIR, threshold)
    if not templates:
        click.secho(f"no templates in {TEMPLATE_DIR}/", fg="yellow")
        return
    for key, template in sorted(templates.items()):
        w, h = template.size
        click.echo(f"  {key:<32} {w:>4}x{h:<4}  threshold {template.threshold}")


@main.command()
@config_option
@verbose_option
@click.option("--dry-run", is_flag=True, help="Tap nothing; log and annotate instead.")
@click.option("--once", is_flag=True, help="Run each task a single time and exit.")
@click.option(
    "--task", "only", type=click.Choice(sorted(REGISTRY)), default=None,
    help="Run just this task, ignoring its enabled flag.",
)
def run(
    config_path: Path | None, verbose: bool, dry_run: bool, once: bool, only: str | None
) -> None:
    """Run the bot.

    Always `--dry-run --once` first: it taps nothing, logs every tap it *would*
    make, and writes annotated screenshots to debug/ so you can confirm the
    boxes are sitting on the right buttons.
    """
    _setup_logging(verbose)
    config = load_config(config_path)

    try:
        bot = _make_bot(config, dry_run=dry_run)
    except AdbError as exc:
        raise click.ClickException(str(exc)) from exc

    if not bot.templates:
        raise click.ClickException(
            f"no templates in {TEMPLATE_DIR}/ - the bot cannot see anything. "
            "Run `avgme capture` and `avgme crop` first."
        )

    expected = config.get("adb", {}).get("expect_resolution")
    if expected:
        width, height = bot.adb.resolution()
        if [width, height] != list(expected):
            raise click.ClickException(
                f"emulator is {width}x{height} but templates were captured at "
                f"{expected[0]}x{expected[1]}. Refusing to run - every template "
                "would miss. Fix the emulator size or recapture templates."
            )

    tasks = build_tasks(config, only=only)
    if not tasks:
        raise click.ClickException("no enabled tasks - check config/tasks.yaml")

    if dry_run:
        click.secho("DRY RUN - nothing will be tapped", fg="yellow", bold=True)

    if once or dry_run:
        run_once(bot, tasks)
        if dry_run:
            path = bot.dump("dry-run", bot.take_dry_run_matches())
            click.secho(f"\nAnnotated result: {path}", fg="cyan")
            click.echo("Open it and check every box is on the button you expect.")
        return

    try:
        run_forever(bot, tasks, config)
    except KeyboardInterrupt:
        click.echo("\nstopped")


if __name__ == "__main__":
    main()
