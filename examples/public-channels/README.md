# Public Channels Over HTTP

This example runs AAAX with a docked system that owns a `PUBLIC` broadcast channel.

The kernel, the docked system, and the default LibOS all run together as one AAAX constellation. What becomes visible on the network is the public channel surface of that running constellation.

## Files

- `aaax.toml` — network host and port for the example
- `run_server.py` — boots the kernel, docks a public event source, and starts HTTP transport

## Run

From the repo root:

```bash
python examples/public-channels/run_server.py
```

The server keeps running until you stop it with `Ctrl+C`.

## Read the Public Channel

In a second terminal:

```bash
curl \
  -H "Authorization: Bearer demo-reader" \
  "http://127.0.0.1:8100/channels/demo-events?limit=5"
```

You can also inspect the channel metadata:

```bash
curl \
  -H "Authorization: Bearer demo-reader" \
  "http://127.0.0.1:8100/channels/demo-events/info"
```

Because this example uses open local security, the Bearer token is just the reader ID.

## Enter the CLI

AAAX does not have an interactive shell yet. The CLI entry point is:

```bash
aaax --help
python -m aaax --help
```

This specific example uses Python instead of `aaax launch ...` because the current CLI does not yet load arbitrary local system classes from config.
