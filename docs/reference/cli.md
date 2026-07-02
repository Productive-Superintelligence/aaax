# CLI

The `aaax` command loads, inspects, and serves strategies.

## Inspect

```bash
aaax inspect TARGET
aaax inspect TARGET --json
```

`TARGET` can be a strategy file, package folder, direct `psi.toml`, directory,
or `module:attribute` value.

Text output lists resource kind, local name, and ref or entrypoint:

```text
analysis-pack: Demo package.
package analysis-pack psi://demo/analysis-pack
tactic echo psi://demo/analysis-pack/tactics/echo
channel events psi://demo/analysis-pack/channels/events
```

## Serve

```bash
aaax serve TARGET --host 127.0.0.1 --port 8400 --log-level info
```

Validation:

- host must be a host name or address, not a URL;
- port must be between `1` and `65535`;
- log level must be one of `critical`, `debug`, `error`, `info`, `trace`, or
  `warning`.

## Launch

```bash
aaax launch TARGET --port 8400
```

`launch` is an alias for `serve` in the current public surface. It exists so
future launch-specific behavior can keep the same command family.
