"""CLI for antidetect-local.

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


app = typer.Typer(add_completion=False, no_args_is_help=True, help="antidetect-local CLI")
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
    console.print(f"[green]antidetect-local[/green] starting on http://{host}:{ui_port}")
    console.print(f"  Dashboard:    http://{host}:{ui_port}/")
    console.print(f"  API docs:     http://{host}:{ui_port}/docs")
    console.print(f"  AdsPower API: http://{host}:{ui_port}/user/list")
    uvicorn.run(app, host=host, port=ui_port, log_level="info")


@app.command("list")
def list_cmd(
    search: Optional[str] = typer.Option(None, "--search", "-s"),
    group: Optional[str] = typer.Option(None, "--group", "-g"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t"),
):
    """List profiles."""
    store = _store()
    profiles = store.list(group_id=group, tag=tag, search=search)
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
):
    """Create a new profile with a generated fingerprint."""
    from .core.fingerprint import generate_fingerprint
    store = _store()
    fp = generate_fingerprint(seed=fingerprint_seed) if fingerprint_seed else generate_fingerprint()
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
        import_root = Path(os.environ.get("ANTIDETECT_DATA_DIR", "data")) / "profiles" / "imports"
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
        "noise_seed": fp.noise[:16],
        "id": fp.id,
    }, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()