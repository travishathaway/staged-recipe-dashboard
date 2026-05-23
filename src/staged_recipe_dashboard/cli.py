"""srdb — staged-recipe-dashboard management CLI."""

import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import typer

from staged_recipe_dashboard.config import RUNTIME_DIR, load_config

app = typer.Typer(name="srdb", help="staged-recipe-dashboard management CLI", no_args_is_help=True)
db_app = typer.Typer(help="Manage the bundled PostgreSQL server", no_args_is_help=True)
app.add_typer(db_app, name="db")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _cfg():
    return load_config()


def _pg_ctl(*args: str, **kwargs) -> subprocess.CompletedProcess:
    cfg = _cfg()
    return subprocess.run(
        ["pg_ctl", *args, "-D", cfg.database.data_dir],
        **kwargs,
    )


def _pg_is_running() -> bool:
    result = _pg_ctl("status", capture_output=True)
    return result.returncode == 0


def _write_pid(name: str, pid: int) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    (RUNTIME_DIR / f"{name}.pid").write_text(str(pid))


def _read_pid(name: str) -> int | None:
    pid_file = RUNTIME_DIR / f"{name}.pid"
    if pid_file.exists():
        return int(pid_file.read_text().strip())
    return None


def _remove_pid(name: str) -> None:
    pid_file = RUNTIME_DIR / f"{name}.pid"
    pid_file.unlink(missing_ok=True)


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


# ── db subcommands ────────────────────────────────────────────────────────────


@db_app.command("start")
def db_start():
    """Start the bundled PostgreSQL server."""
    if _pg_is_running():
        typer.echo("PostgreSQL is already running.")
        return
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    log_file = RUNTIME_DIR / "postgres.log"
    _pg_ctl("start", "-l", str(log_file), check=True)
    typer.echo("PostgreSQL started.")


@db_app.command("stop")
def db_stop():
    """Stop the bundled PostgreSQL server."""
    if not _pg_is_running():
        typer.echo("PostgreSQL is not running.")
        return
    _pg_ctl("stop", check=True)
    typer.echo("PostgreSQL stopped.")


@db_app.command("shell")
def db_shell():
    """Open a psql shell connected to the dashboard database."""
    cfg = _cfg()
    os.execvp("psql", ["psql", "-d", cfg.database.name, "-h", cfg.database.socket_dir])


# ── Top-level commands ────────────────────────────────────────────────────────


@app.command()
def init():
    """Initialize database: initdb, start postgres, create DB, run migrations."""
    cfg = _cfg()
    data_dir = Path(cfg.database.data_dir)

    if not (data_dir / "PG_VERSION").exists():
        typer.echo(f"Initializing PostgreSQL data directory: {data_dir}")
        data_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["initdb", "-D", str(data_dir), "--auth=trust"],
            check=True,
        )
        # Configure postgres to use our runtime dir for the Unix socket.
        socket_dir = Path(cfg.database.socket_dir)
        socket_dir.mkdir(parents=True, exist_ok=True)
        conf = data_dir / "postgresql.conf"
        with open(conf, "a") as f:
            f.write(f"\nunix_socket_directories = '{socket_dir}'\n")
            f.write(f"port = {cfg.database.port}\n")
    else:
        typer.echo("PostgreSQL data directory already initialized, skipping initdb.")

    db_start()

    # Create the application database if it doesn't exist.
    result = subprocess.run(
        ["psql", "-h", cfg.database.socket_dir, "-d", "postgres", "-tAc",
         f"SELECT 1 FROM pg_database WHERE datname='{cfg.database.name}'"],
        capture_output=True, text=True,
    )
    if result.stdout.strip() != "1":
        typer.echo(f"Creating database: {cfg.database.name}")
        subprocess.run(
            ["createdb", "-h", cfg.database.socket_dir, cfg.database.name],
            check=True,
        )

    typer.echo("Running migrations...")
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    typer.echo("Initialization complete.")


@app.command()
def sync():
    """Run a one-shot sync from GitHub to the database."""
    from staged_recipe_dashboard.worker.sync import run_once

    run_once(_cfg())


@app.command()
def worker():
    """Start the background sync worker (APScheduler, blocking)."""
    from staged_recipe_dashboard.worker.scheduler import start_scheduler

    start_scheduler(_cfg())


@app.command()
def serve():
    """Start the FastAPI/uvicorn server."""
    import uvicorn

    cfg = _cfg()
    uvicorn.run(
        "staged_recipe_dashboard.backend.app:create_app",
        factory=True,
        host=cfg.server.host,
        port=cfg.server.port,
        reload=False,
    )


@app.command("build-ui")
def build_ui():
    """Build the Svelte frontend and copy assets into the package static/ dir."""
    project_root = Path(__file__).parent.parent.parent
    frontend_dir = project_root / "frontend"
    static_dir = Path(__file__).parent / "static"

    if not frontend_dir.exists():
        typer.echo("frontend/ directory not found.", err=True)
        raise typer.Exit(1)

    typer.echo("Building frontend...")
    subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True)

    dist_dir = frontend_dir / "dist"
    if static_dir.exists():
        shutil.rmtree(static_dir)
    shutil.copytree(dist_dir, static_dir)
    typer.echo(f"Frontend built and copied to {static_dir}")


@app.command()
def start():
    """Start all components: postgres, background worker, and API server."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    if not _pg_is_running():
        db_start()

    worker_proc = subprocess.Popen(
        [sys.executable, "-m", "staged_recipe_dashboard.cli", "worker"]
    )
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "staged_recipe_dashboard.cli", "serve"]
    )

    _write_pid("worker", worker_proc.pid)
    _write_pid("server", server_proc.pid)

    def _shutdown(sig, frame):
        typer.echo("\nShutting down...")
        worker_proc.terminate()
        server_proc.terminate()
        worker_proc.wait(timeout=10)
        server_proc.wait(timeout=10)
        _pg_ctl("stop")
        _remove_pid("worker")
        _remove_pid("server")
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    typer.echo(
        f"All components running. Worker PID: {worker_proc.pid}, Server PID: {server_proc.pid}"
    )
    typer.echo("Press Ctrl+C to stop.")
    worker_proc.wait()


@app.command()
def stop():
    """Stop the background worker and API server; stop postgres."""
    for name in ("worker", "server"):
        pid = _read_pid(name)
        if pid is None:
            typer.echo(f"{name}: no PID file found")
            continue
        if _process_alive(pid):
            os.kill(pid, signal.SIGTERM)
            typer.echo(f"Stopped {name} (PID {pid})")
        else:
            typer.echo(f"{name}: not running (stale PID file)")
        _remove_pid(name)

    if _pg_is_running():
        _pg_ctl("stop")
        typer.echo("PostgreSQL stopped.")
    else:
        typer.echo("PostgreSQL: not running")


@app.command()
def status():
    """Show running status of all components."""
    pg_status = "running" if _pg_is_running() else "stopped"
    typer.echo(f"postgres : {pg_status}")

    for name in ("worker", "server"):
        pid = _read_pid(name)
        if pid is None:
            typer.echo(f"{name:8}: stopped")
        elif _process_alive(pid):
            typer.echo(f"{name:8}: running (PID {pid})")
        else:
            typer.echo(f"{name:8}: stopped (stale PID file)")


if __name__ == "__main__":
    app()
