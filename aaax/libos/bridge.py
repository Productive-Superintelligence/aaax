from __future__ import annotations

import os

from aaax._vendor import ensure_vendor_paths
from aaax.config import LibOSConfig

ensure_vendor_paths()

from sssn.core.system import BaseSystem


class DefaultLibOS:
    """Thin AAAX-owned bridge to LLLM."""

    def __init__(self, kernel, config: LibOSConfig) -> None:
        self.kernel = kernel
        self.config = config

    def build_runtime(self, module_id: str, toml_path: str):
        os.environ.setdefault("LLLM_AUTO_INIT", "0")
        ensure_vendor_paths()
        from lllm import load_runtime

        return load_runtime(
            toml_path=toml_path,
            name=f"aaax:{module_id}",
            discover_cwd=not self.config.strict_boot,
            discover_shared_packages=self.config.discover_shared_packages,
        )


class TacticSystem(BaseSystem):
    """Minimal SSSN wrapper around an LLLM runtime/tactic package."""

    def __init__(self, id: str, name: str, manifest: dict, libos: DefaultLibOS | None = None) -> None:
        super().__init__(id=id, name=name)
        self.manifest = manifest
        self._libos = libos
        self.runtime = None

    async def setup(self) -> None:
        if self._libos is None:
            raise RuntimeError("TacticSystem requires a DefaultLibOS instance.")
        toml_path = self.manifest.get("lllm_toml")
        if not toml_path:
            raise ValueError(f"LLLM module '{self.id}' missing 'lllm_toml' in manifest.")
        self.runtime = self._libos.build_runtime(self.id, toml_path)

    async def step(self) -> None:
        self.stop()
