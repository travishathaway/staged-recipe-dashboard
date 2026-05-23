"""Application configuration loaded from config.toml."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

_APP_NAME = "staged-recipe-dashboard"

CONFIG_DIR = Path(platformdirs.user_config_dir(_APP_NAME))
DATA_DIR = Path(platformdirs.user_data_dir(_APP_NAME))
RUNTIME_DIR = Path(platformdirs.user_runtime_dir(_APP_NAME))


@dataclass
class DatabaseConfig:
    data_dir: str = str(DATA_DIR / "pgdata")
    port: int = 5432
    name: str = "staged_recipe_dashboard"
    # Socket dir where postgres places its .s.PGSQL.* socket file.
    # Defaults to RUNTIME_DIR; configured via unix_socket_directories in postgresql.conf.
    socket_dir: str = str(RUNTIME_DIR)

    @property
    def url(self) -> str:
        return f"postgresql+psycopg2:///{self.name}?host={self.socket_dir}"

    @classmethod
    def from_dict(cls, d: dict) -> "DatabaseConfig":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class WorkerConfig:
    sync_interval_minutes: int = 15
    events_interval_minutes: int = 60
    github_tokens: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "WorkerConfig":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def from_dict(cls, d: dict) -> "ServerConfig":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class AppConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from TOML file; fall back to defaults if the file doesn't exist."""
    config_path = path or CONFIG_DIR / "config.toml"
    if not config_path.exists():
        return AppConfig()

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    return AppConfig(
        database=DatabaseConfig.from_dict(raw.get("database", {})),
        worker=WorkerConfig.from_dict(raw.get("worker", {})),
        server=ServerConfig.from_dict(raw.get("server", {})),
    )
