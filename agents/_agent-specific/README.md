# Pipeline-internal agents — not for direct invocation

These 6 definitions are **dispatch targets**, not standalone tools.
Each one is invoked by an orchestrating agent as part of a larger
workflow. Invoking one directly will fail or produce nonsense,
because they expect parameters (a scan root, a workspace clone, a
comparison result path) that only the parent workflow supplies.

They are kept here rather than deleted so the pipelines remain
reproducible.

| Agent | Dispatched by | Why it is not standalone | Original source |
|---|---|---|---|
| `analyzer` | skill-creator-plus | eval loop — internal post-hoc analyzer | marketplace:claude-plugins-official |
| `comparator` | skill-creator-plus | eval loop — internal blind comparator | marketplace:claude-plugins-official |
| `documentation-writer` | VS Code Python extension | extension-internal agent | vscode-extension |
| `grader` | skill-creator-plus | eval loop — internal grader | marketplace:claude-plugins-official |
| `logs-reader` | osmo-cli | spawned by the main OSMO agent | plugin:nvidia |
| `workflow-expert` | osmo-cli | spawned by the main OSMO agent | plugin:nvidia |

The "Original source" column names the *container* the agent came
from — the plugin, the marketplace or the project — rather than a
path on the machine that assembled this tree. The full attribution
for every entry is in `mcp/data/provenance.json` and `CREDITS.md`.

