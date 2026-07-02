# Shell

The shell is the callable half of AAAX. After a package or strategy is loaded
and resources are mounted, AAAX exposes a FastAPI app that can be called by
scripts, humans, local tools, and future agent workflows.

```mermaid
flowchart LR
  A["aaax serve"] --> B["load shell"]
  B --> C["mount and bind resources"]
  C --> D["FastAPI app"]
  D --> E["/run"]
  D --> F["/tactics/{name}/run"]
  D --> G["/channels/{name}/events"]
  D --> H["/resources/{name}/invoke"]
```

## CLI Shell

```bash
aaax serve strategy.py --host 127.0.0.1 --port 8400
aaax serve packages/analyst-pack --port 8400
```

`launch` is currently an alias for `serve`:

```bash
aaax launch packages/analyst-pack --port 8400
```

## In-Process Shell

```python
from aaax import create_strategy_app, load_strategy


shell = load_strategy("packages/analyst-pack")
app = create_strategy_app(shell)
```

Then run it with Uvicorn, Hypercorn, or your deployment server.

## Operational Boundary

AAAX validates host, port, and log-level CLI inputs. It does not manage TLS,
replicas, queue workers, secrets, containers, or cloud deployment. Keep those in
the deployment layer and treat AAAX as the shell object that layer serves.
