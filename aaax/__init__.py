from importlib.metadata import PackageNotFoundError, version

from aaax.bootstrap import bootstrap_kernel
from aaax.config import AAAXConfig, LibOSConfig, ModuleConfig, NetworkConfig
from aaax.kernel import AAAXKernel

try:
    __version__ = version("aaax")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "__version__",
    "AAAXConfig",
    "LibOSConfig",
    "ModuleConfig",
    "NetworkConfig",
    "AAAXKernel",
    "bootstrap_kernel",
]
