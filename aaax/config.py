from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def _load_toml(path: str | Path) -> dict[str, Any]:
    try:
        import tomllib  # type: ignore[attr-defined]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

    with open(path, "rb") as handle:
        return tomllib.load(handle)


class NetworkConfig(BaseModel):
    publish: bool = False
    host: str = "0.0.0.0"
    port: int = 8100


class LibOSConfig(BaseModel):
    name: str = "lllm"
    strict_boot: bool = True
    discover_shared_packages: bool = False


class ModuleConfig(BaseModel):
    id: str
    framework: str = "lllm"
    lllm_toml: str | None = None
    channels: list[str] = Field(default_factory=list)
    executors: list[str] = Field(default_factory=list)
    remote_channels: list[str] = Field(default_factory=list)
    manifest: dict[str, Any] | None = None


class AAAXConfig(BaseModel):
    id: str = "aaax-main"
    name: str = "AAAX Kernel"
    policy: str | dict[str, Any] | None = "default"
    libos: LibOSConfig = Field(default_factory=LibOSConfig)
    modules: list[ModuleConfig] = Field(default_factory=list)
    network: NetworkConfig = Field(default_factory=NetworkConfig)

    @classmethod
    def from_file(cls, path: str | Path) -> "AAAXConfig":
        raw = _load_toml(path)
        return cls(**raw.get("aaax", {}))
