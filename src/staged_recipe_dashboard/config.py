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
    sync_interval_minutes: int = 1
    events_interval_minutes: int = 60
    review_sync_interval_minutes: int = 120
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
class LoggingConfig:
    # Path to a log file. When unset, logs go to stderr.
    file: str | None = None
    level: str = "INFO"

    @classmethod
    def from_dict(cls, d: dict) -> "LoggingConfig":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class AuthConfig:
    github_client_id: str = ""
    github_client_secret: str = ""
    # Scheme+host used to build the redirect_uri sent to GitHub.
    # E.g. "https://srdb.example.com" for production, "http://localhost:5173" for dev.
    base_url: str = "http://localhost:5173"

    @classmethod
    def from_dict(cls, d: dict) -> "AuthConfig":
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class AppConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from TOML file; fall back to defaults if no file is found.

    Search order:
      1. Explicit path argument
      2. ./config.toml  (current working directory)
      3. <platform config dir>/config.toml
    """
    candidates = [path] if path else [Path("config.toml"), CONFIG_DIR / "config.toml"]
    config_path = next((p for p in candidates if p and p.exists()), None)

    if config_path is None:
        return AppConfig()

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    return AppConfig(
        database=DatabaseConfig.from_dict(raw.get("database", {})),
        worker=WorkerConfig.from_dict(raw.get("worker", {})),
        server=ServerConfig.from_dict(raw.get("server", {})),
        logging=LoggingConfig.from_dict(raw.get("logging", {})),
        auth=AuthConfig.from_dict(raw.get("auth", {})),
    )
