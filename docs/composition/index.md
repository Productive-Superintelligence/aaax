# Strategy

Strategy is the main reason AAAX exists. A strategy can be as small as a
Pydantic-modeled resource table with local handlers. Around it, LLLM owns
tactics, services, and package manifests, and SSSN owns channels and stores.
AAAX gathers those resources into one shell and exposes them as one command
surface.

<div class="psi-flow">
  <div><strong>Describe</strong><br />Write `lllm.toml` resources.</div>
  <div><strong>Mount</strong><br />Load the package into a shell.</div>
  <div><strong>Bind</strong><br />Attach local tactic and channel handlers.</div>
  <div><strong>Serve</strong><br />Expose the shell as Pydantic/FastAPI.</div>
</div>

## Resource Kinds

AAAX understands the resource kinds of LLLM packages, plus `custom` for
anything else:

- package
- schema
- tactic
- channel
- snapshot
- service
- run
- config
- doc
- example
- asset
- custom

Mounting a package imports every manifest section that matters for launch
context, not only executable tactics.

## Strategy Rules

- Local names must be unique path segments.
- Prefix imported packages when names might collide; clashing names are
  rejected.
- Keep original `lllm://` refs in resource records.
- Treat channels as resources with shell-facing handlers, backed by the
  strategy's one store, not hidden runtime state.
- Treat docs, examples, assets, package cards, and config as first-class context.

## Next

- See the exact resource record in [Strategy Resources](strategy-resources.md).
- Learn manifest import behavior in [LLLM Packages](packages.md).
- Learn channel and service binding in [Channels And Services](channels-services.md).
