# Configuration

AAAX reads a single `[aaax]` table from TOML and maps it into `AAAXConfig`.

## Top-level model

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | `str` | Kernel system ID |
| `name` | `str` | Human-readable kernel name |
| `policy` | `str | dict | None` | Policy selector, inline rules, or file path |
| `libos` | `LibOSConfig` | Default LibOS bridge settings |
| `modules` | `list[ModuleConfig]` | Initial modules to dock |
| `network` | `NetworkConfig` | HTTP publish settings |

## LibOSConfig

| Field | Default | Meaning |
| --- | --- | --- |
| `name` | `lllm` | Default LibOS adapter name |
| `strict_boot` | `true` | Disable ambient LLLM cwd discovery |
| `discover_shared_packages` | `false` | Allow shared-package discovery when explicitly enabled |

## ModuleConfig

| Field | Meaning |
| --- | --- |
| `id` | Module/system ID |
| `framework` | Framework selector, currently `lllm` or a placeholder custom value |
| `lllm_toml` | Path to the module’s `lllm.toml` when using the default LibOS |
| `channels` | Requested local channel wiring |
| `executors` | Requested mediated executors |
| `remote_channels` | Requested remote channels that require capability mediation |
| `manifest` | Full explicit manifest override |

## NetworkConfig

| Field | Default | Meaning |
| --- | --- | --- |
| `publish` | `false` | Whether your AAAX runtime should attach HTTP transport to public channels |
| `host` | `0.0.0.0` | HTTP bind host |
| `port` | `8100` | HTTP bind port |

## Example

```toml
[aaax]
id = "aaax-main"
name = "AAAX Kernel"
policy = "default"

[aaax.libos]
name = "lllm"
strict_boot = true
discover_shared_packages = false

[aaax.network]
publish = false
host = "0.0.0.0"
port = 8100

[[aaax.modules]]
id = "research-analyst"
framework = "lllm"
lllm_toml = "packages/research_analyst/lllm.toml"
channels = ["market-data"]
executors = ["analysis.executor"]
remote_channels = ["sssn://news-provider/market-news"]
```

## Loading config

```python
from aaax import AAAXConfig

config = AAAXConfig.from_file("aaax.toml")
```

AAAX intentionally keeps the config surface small for now. Higher application settings belong in the application layer, not in the kernel config.
