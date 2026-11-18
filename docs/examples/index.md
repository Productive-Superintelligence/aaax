# Examples

Complete programs you can copy and adapt. Each one is a single file that
combines tactics, packages, and channels into one served strategy, with
its output and a short explanation of why it is built that way. The guide
pages teach one feature at a time; these show how the features fit
together.

| Example | What it shows |
| --- | --- |
| [Support desk](support-desk.md) | Tickets arrive on a channel, `POST /run` triages them with an SSSN processor, and every result is recorded and linked to its ticket |
| [Two packages, one API](two-packages.md) | Two LLLM packages mounted under prefixes, sharing one store, joined by a runner, and served as one app |

## Running them

The examples use channels, so they need SSSN, and they call the app with
FastAPI's `TestClient`, which needs `httpx`:

```bash
pip install "aaax[channels]" httpx
python support_desk.py
```

Run each one from an empty folder. It keeps its channels in a store under
`.lllm/network` there, so a second run in the same folder adds to the
first run's events and prints more.

They make no model calls: their tactics are deterministic Python, so they
run offline and print exactly what the pages show. A tactic whose agents
call a model takes the same place in a strategy without other changes
([Tactics](https://lllm.one/tactics/)). Each page also shows how to serve
the strategy with `aaax serve` and call it with `curl`.

More examples live next to the features they teach:
[Channels](../channels.md) runs a tactic over a channel,
[Serving](../serving.md) passes a request context to a tactic, and
[Agents and handoff](../agents.md) turns a served tactic into a tool for an
LLLM agent.
