# Strategy

Strategy is the main reason AAAX exists. LLLM owns tactic boundaries, SSSN
owns channels and stores, and PsiHub owns package manifests. AAAX gathers those
resources into one shell and exposes them as one command surface.

<div class="psi-flow">
  <div><strong>Describe</strong><br />Write `psi.toml` resources.</div>
  <div><strong>Mount</strong><br />Load the package into a shell.</div>
  <div><strong>Bind</strong><br />Attach local tactic and channel handlers.</div>
  <div><strong>Serve</strong><br />Expose the shell as FastAPI.</div>
</div>

## Resource Kinds

AAAX understands the package-facing resource kinds used by the PSI stack:

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

The built-in package bridge imports all of the PsiHub manifest sections that
matter for launch context, not only executable tactics.

## Strategy Rules

- Local names must be path-segment friendly.
- Prefix imported packages when names might collide.
- Keep original `psi://` refs in resource records.
- Treat channels as resources with shell-facing handlers, not hidden runtime state.
- Treat docs, examples, assets, package cards, and config as first-class context.

## Next

- See the exact resource record in [Strategy Resources](strategy-resources.md).
- Learn manifest import behavior in [PsiHub Packages](psihub-packages.md).
- Learn channel and service binding in [Channels And Services](channels-services.md).
