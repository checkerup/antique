"""CLI for antique.

Subcommands:

    serve             Run the API + UI server
    list              List profiles
    create            Create a profile
    start             Start a profile's browser
    stop              Stop a profile's browser
    delete            Delete a profile
    import-cookies    Import cookies from a file → create a profile (--full for full .adb import)
    import-backup     Import an entire AdsPower backup directory via all_profiles_list.json
    reimport          Reset the full-profile state for a profile
    export-cookies    Export a profile's cookies
    fingerprint       Generate and print a fingerprint JSON (for debugging)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table


def force_utf8_stdio(streams=None) -> list:
    """Reconfigure stdio streams to UTF-8 so Unicode glyphs (✓, ✗, …) don't
    crash on legacy Windows codepages (cp1251/cp866) in PowerShell / cmd.

    Without this, printing a check mark raises:
        UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'

    Returns the list of stream names successfully reconfigured (for testing).
    Safe to call unconditionally: streams that don't support ``reconfigure``
    (already-UTF-8 or wrapped) are skipped silently.
    """
    if streams is None:
        streams = [getattr(sys, name, None) for name in ("stdout", "stderr")]
    done = []
    for stream in streams:
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
            done.append(getattr(stream, "name", repr(stream)))
        except Exception:
            pass
    return done


# Apply as early as possible so every command's output is UTF-8 safe.
force_utf8_stdio()

app = typer.Typer(add_completion=False, no_args_is_help=True, help="antique CLI")
# ``Console`` with an explicit legacy_windows=False + safe box keeps Rich from
# falling back to the console codepage. errors are already handled by the
# stdio reconfigure above.
console = Console()


def _store():
    """Lazy-loaded ProfileStore."""
    from .core.profile import ProfileStore
    return ProfileStore()


def _print_profile(p) -> None:
    console.print(f"[bold]{p.name}[/bold]  [dim]({p.user_id})[/dim]")
    console.print(f"  group: {p.group_id}   launches: {p.launch_count}   cookies: {len(p.cookies)}")
    if p.proxy:
        console.print(f"  proxy: {p.proxy.get('proxy_type')}://{p.proxy.get('proxy_host')}:{p.proxy.get('proxy_port')}")
    if p.tags:
        console.print(f"  tags: {', '.join(p.tags)}")


@app.command()
def serve(
    api_port: int = typer.Option(50325, "--api-port", help="(unused) AdsPower-compat port for docs"),
    ui_port: int = typer.Option(8080, "--ui-port", "-p", help="Web UI port"),
    cdp_port: int = typer.Option(5555, "--cdp-port", help="CDP multiplexer port"),
    host: str = typer.Option("127.0.0.1", "--host"),
    headless: bool = typer.Option(False, "--headless"),
):
    """Run the API + UI server."""
    from .api.server import create_app
    import uvicorn
    app = create_app(api_port=api_port, cdp_port=cdp_port, headless=headless)
    console.print(f"[green]antique[/green] starting on http://{host}:{ui_port}")
    console.print(f"  Dashboard:    http://{host}:{ui_port}/")
    console.print(f"  API docs:     http://{host}:{ui_port}/docs")
    console.print(f"  AdsPower API: http://{host}:{ui_port}/user/list")
    uvicorn.run(app, host=host, port=ui_port, log_level="info")


@app.command("list")
def list_cmd(
    search: Optional[str] = typer.Option(None, "--search", "-s"),
    group: Optional[str] = typer.Option(None, "--group", "-g"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t"),
    sort_by: str = typer.Option("name", "--sort", help="name|id|group|status|tags|launches|cookies|created|updated|last_launched|proxy|engine|live"),
    sort_order: str = typer.Option("asc", "--order", help="asc|desc"),
):
    """List profiles with filters and sorting."""
    store = _store()
    profiles = store.list(group_id=group, tag=tag, search=search, sort_by=sort_by, sort_order=sort_order)
    if not profiles:
        console.print("[yellow]No profiles yet.[/yellow] Use `antidetect create` to make one.")
        raise typer.Exit(0)
    t = Table(title=f"Profiles ({len(profiles)})")
    t.add_column("user_id", style="cyan", no_wrap=True)
    t.add_column("name", style="bold")
    t.add_column("group")
    t.add_column("tags")
    t.add_column("proxy")
    t.add_column("cookies", justify="right")
    t.add_column("launched", justify="right")
    for p in profiles:
        proxy = "—"
        if p.proxy and p.proxy.get("proxy_type") != "direct":
            proxy = f"{p.proxy.get('proxy_type')}://{p.proxy.get('proxy_host')}:{p.proxy.get('proxy_port')}"
        t.add_row(
            p.user_id,
            p.name,
            p.group_id,
            ", ".join(p.tags),
            proxy,
            str(len(p.cookies)),
            str(p.launch_count),
        )
    console.print(t)


@app.command("clone")
def clone_cmd(
    user_id: str = typer.Argument(...),
    name: Optional[str] = typer.Option(None, "--name", "-n"),
    user_id_override: Optional[str] = typer.Option(None, "--user-id"),
):
    """Clone a profile's metadata, cookies, proxy and fingerprint."""
    store = _store()
    source = store.get(user_id)
    if source is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    from dataclasses import fields
    from .core.fingerprint import Fingerprint
    valid = {f.name for f in fields(Fingerprint)}
    fp = Fingerprint(**{k: v for k, v in source.fingerprint.items() if k in valid})
    try:
        clone = store.create(name=name or f"{source.name} copy", group_id=source.group_id, proxy=dict(source.proxy), fingerprint=fp, cookies=list(source.cookies), tags=list(source.tags), remark=source.remark, user_id=user_id_override)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    console.print(f"[green]✓[/green] cloned {source.name} → [cyan]{clone.user_id}[/cyan]")


@app.command("bulk-status")
def bulk_status_cmd(
    user_ids: list[str] = typer.Argument(...),
    status: str = typer.Argument(...),
):
    """Set one account status for several profiles."""
    store = _store()
    updated = 0
    for uid in user_ids:
        try:
            store.update(uid, account_status=status)
            updated += 1
        except KeyError:
            console.print(f"[yellow]skip {uid}: not found[/yellow]")
    console.print(f"[green]✓[/green] updated {updated}/{len(user_ids)} profiles → {status}")


@app.command()
def create(
    name: str = typer.Argument(...),
    group: str = typer.Option("0", "--group", "-g"),
    proxy_type: str = typer.Option("direct", "--proxy-type"),
    proxy_host: Optional[str] = typer.Option(None, "--proxy-host"),
    proxy_port: Optional[int] = typer.Option(None, "--proxy-port"),
    proxy_user: Optional[str] = typer.Option(None, "--proxy-user"),
    proxy_password: Optional[str] = typer.Option(None, "--proxy-password"),
    remark: str = typer.Option("", "--remark", "-r"),
    tags: str = typer.Option("", "--tags", help="Comma-separated"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    fingerprint_seed: Optional[str] = typer.Option(None, "--fingerprint-seed"),
    geo_country: Optional[str] = typer.Option(None, "--geo-country", help="ISO country (US, DE, RU…) to align timezone/locale/geolocation"),
    engine: Optional[str] = typer.Option(None, "--engine", help="Browser engine: chromium|chrome|edge|firefox|camoufox|webkit"),
    status: str = typer.Option("new", "--status", help="Account status: new|warming|active|limited|banned|retired"),
):
    """Create a new profile with a generated fingerprint."""
    from .core.fingerprint import generate_fingerprint
    store = _store()
    fp = generate_fingerprint(seed=fingerprint_seed) if fingerprint_seed else generate_fingerprint()
    if geo_country:
        from .core.geo import geo_for_country, apply_geo_to_fingerprint
        apply_geo_to_fingerprint(fp, geo_for_country(geo_country))
    if engine:
        from .core.engines import is_valid_engine, engine_keys
        if not is_valid_engine(engine):
            console.print(f"[red]Unknown engine {engine!r}. Valid: {', '.join(engine_keys())}[/red]")
            raise typer.Exit(1)
        fp.browser_engine = engine.lower()
    proxy: dict = {"proxy_type": proxy_type}
    if proxy_type != "direct":
        if not (proxy_host and proxy_port):
            console.print("[red]Proxy host and port required for non-direct proxy[/red]")
            raise typer.Exit(1)
        proxy.update({"proxy_host": proxy_host, "proxy_port": proxy_port})
        if proxy_user:
            proxy["proxy_user"] = proxy_user
        if proxy_password:
            proxy["proxy_password"] = proxy_password
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    p = store.create(
        name=name,
        group_id=group,
        proxy=proxy,
        fingerprint=fp,
        tags=tag_list,
        remark=remark,
        account_status=status,
        user_id=user_id,
    )
    console.print(f"[green]✓[/green] created profile [bold]{p.name}[/bold] with id [cyan]{p.user_id}[/cyan]")
    console.print(f"  fingerprint id: [dim]{fp.id}[/dim]")


@app.command()
def start(
    user_id: str = typer.Argument(...),
    debug_port: Optional[int] = typer.Option(None, "--port"),
):
    """Start the browser for a profile."""
    import asyncio
    from .core.browser import BrowserLauncher
    store = _store()
    launcher = BrowserLauncher(store)
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    async def _go():
        h = await launcher.start(p, debug_port=debug_port)
        console.print(f"[green]✓[/green] started {p.name} on debug port {h.debug_port}")
        console.print(f"  WS: [cyan]{h.ws_endpoint}[/cyan]")
    asyncio.run(_go())


@app.command()
def stop(
    user_id: str = typer.Argument(...),
):
    """Stop the browser for a profile."""
    import asyncio
    from .core.browser import BrowserLauncher
    store = _store()
    launcher = BrowserLauncher(store)
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    async def _go():
        ok = await launcher.stop(user_id)
        if ok:
            console.print(f"[green]✓[/green] stopped {p.name}")
        else:
            console.print(f"[yellow]No running browser for {p.name}[/yellow]")
    asyncio.run(_go())


@app.command()
def delete(
    user_id: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
    """Delete a profile."""
    store = _store()
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    if not yes:
        confirm = typer.confirm(f"Delete profile '{p.name}' ({user_id})?")
        if not confirm:
            raise typer.Abort()
    store.delete(user_id)
    console.print(f"[green]✓[/green] deleted {p.name}")


@app.command("import-cookies")
def import_cookies(
    path: Path = typer.Argument(..., exists=True, dir_okay=True),
    name: Optional[str] = typer.Option(None, "--name", "-n"),
    proxy_type: str = typer.Option("direct", "--proxy-type"),
    proxy_host: Optional[str] = typer.Option(None, "--proxy-host"),
    proxy_port: Optional[int] = typer.Option(None, "--proxy-port"),
    full: bool = typer.Option(
        False,
        "--full",
        help="Full profile import: extract the .adb bundle and apply "
        "LocalStorage + IndexedDB on first launch. Defaults to cookies-only.",
    ),
):
    """Import cookies from a file (Netscape/JSON/AdsPower bundle) → new profile.

    With ``--full``, the bundle is extracted under ``data/profiles/imports/<user_id>/``
    and the launcher copies its ``Local Storage/leveldb`` + ``IndexedDB`` into the
    Playwright user_data_dir before the first launch.
    """
    from .core.cookie import import_cookies, prepare_adspower_import
    from .core.fingerprint import generate_fingerprint
    store = _store()
    is_full = bool(full) or path.is_dir() or path.suffix.lower() in (
        ".adb", ".zip", ".tar", ".tgz",
    ) or path.name.endswith(".tar.gz")

    if is_full:
        # Full-profile flow: create the profile first (so we have a user_id),
        # then extract the bundle under data/profiles/imports/<user_id>/.
        p = store.create(name=name or path.stem)
        import_root = Path(os.environ.get("ANTIQUE_DATA_DIR", "data")) / "profiles" / "imports"
        import_root.mkdir(parents=True, exist_ok=True)
        try:
            result = prepare_adspower_import(path, import_root, p.user_id)
        except ValueError as exc:
            console.print(f"[red]Bundle format error: {exc}[/red]")
            store.delete(p.user_id)
            raise typer.Exit(1)
        cookies = result["cookies"]
        extracted_path = result["extracted_path"]
        default_dir = result["default_dir"]
        store.update(p.user_id, cookies=[c.to_playwright() for c in cookies])
        store.set_import_source(p.user_id, extracted_path)
        console.print(
            f"[green]✓[/green] imported [bold]{len(cookies)}[/bold] cookies → "
            f"profile [cyan]{p.user_id}[/cyan] ({p.name})"
        )
        console.print(f"  extracted bundle: [dim]{extracted_path}[/dim]")
        if default_dir:
            console.print(f"  Default/ dir:     [dim]{default_dir}[/dim]")
            ls = Path(default_dir) / "Local Storage" / "leveldb"
            idb = Path(default_dir) / "IndexedDB"
            if ls.exists():
                console.print("  [green]+[/green] LocalStorage will be applied on first launch")
            if idb.exists():
                console.print("  [green]+[/green] IndexedDB will be applied on first launch")
        return

    # Cookies-only flow
    cookies = import_cookies(path)
    if not cookies:
        console.print(f"[red]No cookies found in {path}[/red]")
        raise typer.Exit(1)
    cookie_dicts = [c.to_playwright() for c in cookies]
    fp = generate_fingerprint()
    proxy: dict = {"proxy_type": proxy_type}
    if proxy_type != "direct":
        if not (proxy_host and proxy_port):
            console.print("[red]Proxy host/port required[/red]")
            raise typer.Exit(1)
        proxy.update({"proxy_host": proxy_host, "proxy_port": proxy_port})
    p = store.create(
        name=name or path.stem,
        proxy=proxy,
        fingerprint=fp,
        cookies=cookie_dicts,
    )
    console.print(f"[green]✓[/green] imported [bold]{len(cookies)}[/bold] cookies → profile [cyan]{p.user_id}[/cyan] ({p.name})")


@app.command("import-backup")
def import_backup(
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    overwrite: bool = typer.Option(False, "--overwrite", help="Update existing profiles if they already exist"),
    limit: Optional[int] = typer.Option(None, "--limit", min=1, help="Import only the first N entries from all_profiles_list.json"),
):
    """Import a full AdsPower backup directory with many profiles."""
    from .core.backup_import import import_adspower_backup_root

    store = _store()
    summary = import_adspower_backup_root(path, store, overwrite=overwrite, limit=limit)
    console.print(
        f"[green]✓[/green] processed {summary['processed']} entries: "
        f"[bold]{summary['imported_count']}[/bold] imported, "
        f"[bold]{summary['updated_count']}[/bold] updated, "
        f"[bold]{summary['skipped_count']}[/bold] skipped, "
        f"[bold]{summary['error_count']}[/bold] errors"
    )
    console.print(
        "  cookies: "
        f"json={summary['cookie_sources'].get('json', 0)} · "
        f"profile_dir={summary['cookie_sources'].get('profile_dir', 0)} · "
        f"none={summary['cookie_sources'].get('none', 0)}"
    )
    console.print(f"  full-state profiles: {summary['full_state_profiles']}")
    if summary["errors"]:
        for err in summary["errors"][:10]:
            console.print(f"  [red]-[/red] {err['user_id']}: {err['error']}")


@app.command("preview-backup")
def preview_backup_cmd(path: Path = typer.Argument(..., exists=True, file_okay=False)):
    """Preview an AdsPower backup without writing profiles."""
    from .core.operations import preview_backup
    data = preview_backup(path)
    console.print_json(json.dumps(data, ensure_ascii=False, default=str))


@app.command("template-create")
def template_create_cmd(template_file: Path = typer.Argument(..., exists=True, dir_okay=False), count: int = typer.Option(1, "--count"), seed: Optional[str] = typer.Option(None, "--seed")):
    """Create many profiles from a JSON template."""
    from .core.operations import create_from_template
    result = create_from_template(_store(), json.loads(template_file.read_text(encoding="utf-8")), count, seed=seed)
    console.print(f"[green]✓[/green] created {len(result)} profiles")


@app.command("snapshot-export")
def snapshot_export_cmd(path: Path = typer.Argument(...), password: str = typer.Option(..., prompt=True, hide_input=True)):
    """Write an encrypted profile snapshot."""
    from .core.operations import encrypted_snapshot
    encrypted_snapshot(_store(), path, password)
    console.print(f"[green]✓[/green] encrypted snapshot → {path}")


@app.command("snapshot-import")
def snapshot_import_cmd(path: Path = typer.Argument(..., exists=True), password: str = typer.Option(..., prompt=True, hide_input=True), overwrite: bool = typer.Option(False, "--overwrite")):
    """Restore an encrypted profile snapshot."""
    from .core.operations import decrypt_snapshot
    result = decrypt_snapshot(_store(), path, password, overwrite=overwrite)
    console.print_json(json.dumps(result))


@app.command("backup-schedule")
def backup_schedule_cmd(destination: Path = typer.Argument(...), interval_minutes: int = typer.Option(1440, "--interval-minutes", min=5)):
    """Register a local encrypted backup schedule."""
    from .core.backup_scheduler import add_schedule
    item = add_schedule(_store(), str(destination), interval_minutes)
    console.print_json(json.dumps(item.__dict__))


@app.command("backup-schedules")
def backup_schedules_cmd():
    """List registered backup schedules."""
    from .core.backup_scheduler import list_schedules
    console.print_json(json.dumps([x.__dict__ for x in list_schedules(_store())]))


@app.command("activity")
def activity_cmd(user_id: Optional[str] = typer.Option(None, "--user"), limit: int = typer.Option(100, "--limit")):
    """Show profile audit history."""
    from .core.operations import list_activity
    console.print_json(json.dumps([a.__dict__ for a in list_activity(_store(), user_id, limit)], ensure_ascii=False))


@app.command("reimport")
def reimport(
    user_id: str = typer.Argument(...),
):
    """Reset the full-profile state for an existing profile so the next launch
    re-copies LocalStorage + IndexedDB from the saved bundle path."""
    store = _store()
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    if not p.import_source_path:
        console.print(
            f"[yellow]Profile {user_id} has no import_source_path. "
            "Run `antidetect import-cookies --full` first.[/yellow]"
        )
        raise typer.Exit(1)
    store.set_import_source(user_id, p.import_source_path, reset_applied=True)
    console.print(
        f"[green]✓[/green] reset [cyan]{user_id}[/cyan] — next launch will re-apply state from [dim]{p.import_source_path}[/dim]"
    )


@app.command("export-cookies")
def export_cookies(
    user_id: str = typer.Argument(...),
    format: str = typer.Option("json", "--format", "-f", help="json or netscape"),
    out: Optional[Path] = typer.Option(None, "--out", "-o"),
):
    """Export a profile's cookies."""
    from .core.cookie import (
        Cookie,
        export_cookies_json,
        export_cookies_netscape,
    )
    store = _store()
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    cookies = [
        Cookie(
            name=c.get("name", ""),
            value=c.get("value", ""),
            domain=c.get("domain", ""),
            path=c.get("path", "/"),
            expires=float(c.get("expires", -1)),
            http_only=bool(c.get("httpOnly", c.get("http_only", False))),
            secure=bool(c.get("secure", False)),
            same_site=c.get("sameSite", c.get("same_site", "Lax")),
        )
        for c in p.cookies
    ]
    text = export_cookies_netscape(cookies) if format == "netscape" else export_cookies_json(cookies)
    if out:
        out.write_text(text, encoding="utf-8")
        console.print(f"[green]✓[/green] wrote {len(cookies)} cookies → {out}")
    else:
        sys.stdout.write(text)


@app.command("export-profile")
def export_profile_cmd(
    user_id: str = typer.Argument(...),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output .antq file (defaults to <user_id>.antq)"),
):
    """Export a profile to a portable .antq bundle (fingerprint+proxy+cookies+tags)."""
    from .core.portable import export_profile
    store = _store()
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    dest = out or Path(f"{user_id}.antq")
    written = export_profile(p, dest)
    console.print(f"[green]✓[/green] exported [bold]{p.name}[/bold] → [cyan]{written}[/cyan]")


@app.command("import-profile")
def import_profile_cmd(
    path: Path = typer.Argument(..., exists=True, dir_okay=False),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Override the imported profile's name"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
):
    """Import a profile from a portable .antq bundle → new profile."""
    from .core.portable import import_profile, PortableBundleError
    store = _store()
    try:
        p = import_profile(store, path, name=name, user_id=user_id)
    except PortableBundleError as exc:
        console.print(f"[red]Bad bundle: {exc}[/red]")
        raise typer.Exit(1)
    console.print(
        f"[green]✓[/green] imported [bold]{p.name}[/bold] → id [cyan]{p.user_id}[/cyan] "
        f"({len(p.cookies)} cookies)"
    )


@app.command("geo-match")
def geo_match(
    user_id: str = typer.Argument(...),
    country: Optional[str] = typer.Option(None, "--country", "-c", help="ISO country code (US, DE, RU…). If omitted, derived from the profile's proxy country field."),
):
    """Align a profile's timezone/locale/languages/geolocation to a country
    (or to its proxy's exit country)."""
    from .core.fingerprint import Fingerprint
    from dataclasses import fields as _fields, asdict
    from .core.geo import geo_for_country, geo_from_proxy, apply_geo_to_fingerprint
    store = _store()
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    # Rebuild the Fingerprint object from the stored dict.
    valid = {f.name for f in _fields(Fingerprint)}
    fp = Fingerprint(**{k: v for k, v in (p.fingerprint or {}).items() if k in valid})
    if country:
        geo = geo_for_country(country)
    else:
        geo = geo_from_proxy(p.proxy)
        if geo is None:
            console.print("[yellow]No --country given and proxy has no country. Nothing to match.[/yellow]")
            raise typer.Exit(1)
    apply_geo_to_fingerprint(fp, geo)
    store.update(user_id, fingerprint=fp)
    console.print(
        f"[green]✓[/green] {p.name}: aligned to [cyan]{geo.country}[/cyan] "
        f"(tz={geo.timezone}, locale={geo.locale}, geo={geo.latitude},{geo.longitude})"
    )


@app.command("proxy-rotate")
def proxy_rotate(
    user_id: str = typer.Argument(...),
    pool_file: Path = typer.Argument(..., exists=True, dir_okay=False, help="Text file with a proxy list (one per line)"),
    strategy: str = typer.Option("round_robin", "--strategy", "-s", help="sticky | round_robin | random"),
):
    """Pick the next proxy from a pool file and assign it to the profile."""
    from .core.proxy_pool import ProxyPool
    from .core.proxy import adspower_shape
    store = _store()
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    try:
        pool = ProxyPool.from_list_text(pool_file.read_text(encoding="utf-8"), strategy=strategy)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    chosen = pool.next_proxy()
    if chosen is None:
        console.print("[red]No live proxy in the pool[/red]")
        raise typer.Exit(1)
    store.update(user_id, proxy=adspower_shape(chosen))
    console.print(
        f"[green]✓[/green] {p.name}: assigned [cyan]{chosen.type}://{chosen.host}:{chosen.port}[/cyan] "
        f"(strategy={strategy})"
    )


@app.command("warm")
def warm(
    user_id: str = typer.Argument(...),
    urls: Optional[Path] = typer.Option(None, "--urls", help="Text file with one URL per line"),
    url: Optional[list[str]] = typer.Option(None, "--url", help="URL to visit (repeatable)"),
    dwell_min_ms: int = typer.Option(2000, "--dwell-min"),
    dwell_max_ms: int = typer.Option(6000, "--dwell-max"),
    scrolls: int = typer.Option(3, "--scrolls"),
    headless: bool = typer.Option(False, "--headless"),
):
    """Cookie Robot: visit a list of URLs to accumulate cookies + localStorage."""
    import asyncio
    from .core.automation import cookie_robot_flow, FlowRunner, FlowValidationError
    from .core.browser import BrowserLauncher
    store = _store()
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    url_list: list[str] = list(url or [])
    if urls:
        url_list += [ln.strip() for ln in urls.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not url_list:
        console.print("[red]Provide --url and/or --urls with at least one URL[/red]")
        raise typer.Exit(1)
    try:
        flow = cookie_robot_flow(
            url_list, dwell_min_ms=dwell_min_ms, dwell_max_ms=dwell_max_ms, scrolls=scrolls
        )
    except FlowValidationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    launcher = BrowserLauncher(store, headless=headless)

    async def _go():
        h = await launcher.start(p)
        try:
            page = await h.context.new_page()
            runner = FlowRunner(page)
            res = await runner.run(flow)
            console.print(
                f"[green]✓[/green] warmed {p.name}: {res.completed}/{len(res.results)} steps ok"
            )
        finally:
            await launcher.stop(user_id)
    asyncio.run(_go())


@app.command("run-flow")
def run_flow(
    user_id: str = typer.Argument(...),
    flow_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    stop_on_error: bool = typer.Option(False, "--stop-on-error"),
    headless: bool = typer.Option(False, "--headless"),
):
    """Run a JSON automation flow (list of steps) against a profile's browser."""
    import asyncio
    from .core.automation import parse_flow, FlowRunner, FlowValidationError
    from .core.browser import BrowserLauncher
    store = _store()
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    try:
        flow = parse_flow(json.loads(flow_file.read_text(encoding="utf-8")))
    except (FlowValidationError, json.JSONDecodeError) as exc:
        console.print(f"[red]Invalid flow: {exc}[/red]")
        raise typer.Exit(1)
    launcher = BrowserLauncher(store, headless=headless)

    async def _go():
        h = await launcher.start(p)
        try:
            page = await h.context.new_page()
            runner = FlowRunner(page, stop_on_error=stop_on_error)
            res = await runner.run(flow)
            for r in res.results:
                mark = "[green]✓[/green]" if r.ok else "[red]✗[/red]"
                console.print(f"  {mark} [{r.index}] {r.action}" + (f"  [red]{r.error}[/red]" if r.error else ""))
            console.print(f"[bold]{res.completed}/{len(res.results)}[/bold] steps ok")
        finally:
            await launcher.stop(user_id)
    asyncio.run(_go())


@app.command("detect-test")
def detect_test(
    user_id: str = typer.Argument(...),
    url: str = typer.Option("about:blank", "--url", help="Page to run the collector on (a local/hosted CreepJS works too)"),
    headless: bool = typer.Option(False, "--headless"),
):
    """Run the stealth self-test harness against a profile and print a graded report."""
    import asyncio
    from dataclasses import fields as _fields
    from .core.browser import BrowserLauncher
    from .core.detect import build_collector_script, score_report, expected_from_fingerprint
    from .core.fingerprint import Fingerprint
    store = _store()
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    valid = {f.name for f in _fields(Fingerprint)}
    fp = Fingerprint(**{k: v for k, v in (p.fingerprint or {}).items() if k in valid})
    launcher = BrowserLauncher(store, headless=headless)

    async def _go():
        h = await launcher.start(p)
        try:
            page = await h.context.new_page()
            if url and url != "about:blank":
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                except Exception:
                    pass
            signals = await page.evaluate(build_collector_script())
            report = score_report(signals, expected=expected_from_fingerprint(fp))
            d = report.to_dict()
            grade_color = "green" if d["grade"] in ("A", "B") else "yellow" if d["grade"] == "C" else "red"
            console.print(f"[bold]Stealth score:[/bold] {d['score']}/100  [{grade_color}]grade {d['grade']}[/{grade_color}]  ({d['passed']}/{d['total']} checks)")
            for c in d["failures"]:
                console.print(f"  [red]✗[/red] [{c['severity']}] {c['name']}: {c['detail']}")
            if not d["failures"]:
                console.print("  [green]✓[/green] no leaks detected")
        finally:
            await launcher.stop(user_id)
    asyncio.run(_go())


@app.command("set-status")
def set_status(
    user_id: str = typer.Argument(...),
    status: str = typer.Argument(..., help="new|warming|active|limited|banned|retired (free-form)"),
):
    """Set a profile's account status."""
    store = _store()
    p = store.get(user_id)
    if p is None:
        console.print(f"[red]user_id {user_id} not found[/red]")
        raise typer.Exit(1)
    store.update(user_id, account_status=status)
    console.print(f"[green]✓[/green] {p.name}: status → [cyan]{status}[/cyan]")


@app.command("sync")
def sync_cmd(
    flow_file: Path = typer.Argument(..., exists=True, dir_okay=False, help="JSON automation flow"),
    user_id: list[str] = typer.Option(..., "--user", "-u", help="Profile to include (repeatable)"),
    stop_on_error: bool = typer.Option(False, "--stop-on-error"),
    max_concurrency: int = typer.Option(0, "--max-concurrency", help="0 = unlimited"),
    headless: bool = typer.Option(False, "--headless"),
):
    """Run one automation flow across several profiles at once (sync group)."""
    import asyncio
    from .core.automation import parse_flow, FlowValidationError
    from .core.sync import run_sync
    from .core.browser import BrowserLauncher
    store = _store()
    try:
        steps = parse_flow(json.loads(flow_file.read_text(encoding="utf-8")))
    except (FlowValidationError, json.JSONDecodeError) as exc:
        console.print(f"[red]Invalid flow: {exc}[/red]")
        raise typer.Exit(1)
    launcher = BrowserLauncher(store, headless=headless)

    async def _go():
        started = []
        for uid in user_id:
            p = store.get(uid)
            if p is None:
                console.print(f"[yellow]skip {uid}: not found[/yellow]")
                continue
            await launcher.start(p)
            started.append(uid)

        async def _page_for(uid):
            h = launcher.get_handle(uid)
            if h is None:
                raise RuntimeError("not running")
            return await launcher._active_page(h)

        report = await run_sync(started, steps, _page_for,
                                stop_on_error=stop_on_error, max_concurrency=max_concurrency)
        for r in report.results:
            mark = "[green]✓[/green]" if r.ok else "[red]✗[/red]"
            console.print(f"  {mark} {r.user_id}: {r.completed}/{r.total}" + (f"  [red]{r.error}[/red]" if r.error else ""))
        console.print(f"[bold]{report.succeeded}/{len(report.results)}[/bold] profiles ok")
        for uid in started:
            await launcher.stop(uid)
    asyncio.run(_go())


@app.command("engines")
def engines_cmd():
    """List available browser engines and their stealth tier."""
    from .core.engines import list_engines
    t = Table(title="Browser engines")
    t.add_column("key", style="cyan", no_wrap=True)
    t.add_column("label")
    t.add_column("base")
    t.add_column("stealth")
    t.add_column("install")
    for e in list_engines():
        t.add_row(e.key, e.label, e.base, e.stealth, "needed" if e.needs_install else "bundled")
    console.print(t)
    console.print("[dim]Set per profile with `create --engine <key>` or globally via ANTIDETECT_ENGINE.[/dim]")


@app.command("mcp")
def mcp_serve(
    transport: str = typer.Option("stdio", "--transport", "-t", help="Transport: stdio"),
):
    """Start the MCP server for AI agent integration (Claude Desktop, Cursor, etc.).

    The MCP server exposes tools for browser automation:
    list_profiles, open_browser, close_browser, navigate, screenshot,
    execute_script, get_cookies, set_cookies, check_proxy.
    """
    import asyncio
    from .mcp.server import run_stdio_server
    console.print("[green]antique MCP[/green] starting on stdio...")
    console.print("  Tools: list_profiles, open_browser, close_browser, navigate, screenshot, execute_script, get/set_cookies, check_proxy")
    asyncio.run(run_stdio_server())


@app.command()
def fingerprint(
    seed: Optional[str] = typer.Option(None, "--seed"),
    os_family: str = typer.Option("windows", "--os"),
):
    """Print a generated fingerprint JSON (for inspection / debugging)."""
    from .core.fingerprint import generate_fingerprint
    fp = generate_fingerprint(seed=seed, os_family=os_family)
    console.print_json(json.dumps({
        "user_agent": fp.user_agent,
        "platform": fp.platform,
        "vendor": fp.vendor,
        "screen": f"{fp.screen_width}x{fp.screen_height}@{fp.pixel_ratio}x",
        "timezone": fp.timezone,
        "locale": fp.locale,
        "languages": fp.languages,
        "webgl": f"{fp.webgl_vendor} / {fp.webgl_renderer}",
        "webgpu": (f"{fp.webgpu_vendor}/{fp.webgpu_architecture} ({fp.webgpu_description})" if fp.webgpu_enabled else "disabled"),
        "fonts": f"{len(fp.fonts)} installed",
        "geolocation": (f"{fp.geo_latitude},{fp.geo_longitude}" if fp.spoof_geolocation else "off"),
        "noise_seed": fp.noise[:16],
        "id": fp.id,
    }, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()