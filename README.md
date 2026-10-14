<p align="center">
  <img src="pearl.png" alt="Pearl of Wisdom logo" width="280">
</p>

<h1 align="center">Pearl of Wisdom</h1>

Pearl of Wisdom gives coding agents a small, inspectable place to do uncertainty work. It can run a quick calculation without creating state, or keep a multi-turn investigation in SQLite when the work grows.

The name honors Judea Pearl. This project is not affiliated with him.

The distribution and command are named `pearl-of-wisdom`. Python code imports `pearl_of_wisdom`.

## Current scope

The Python package has no runtime dependencies. It provides:

- a JSON command-line interface;
- SQLite investigations with separate context, assumptions, evidence, and analyses;
- bounded, seeded Monte Carlo simulation for independent numeric inputs;
- exact enumeration for small discrete Bayesian networks;
- expected utility, regret, and the value of perfect or sample information;
- interventions in explicitly supplied discrete causal models;
- bounded, seeded simulation of a FIFO worker queue with contention, retries, and waiting timeouts.

The repository also contains a shared [Codex and Claude plugin](plugins/pearl-of-wisdom) with two skills:

- `reasoning-under-uncertainty` decides whether a question calls for an exact calculation, bounds, sensitivity analysis, Monte Carlo, discrete Bayes, causal inference, decision analysis, system simulation, or no model;
- `pearl-of-wisdom` manages durable investigation records through the CLI.

The routing skill has a deliberately low activation floor. A quick bound or sensitivity check can help before an experiment becomes production behavior. It also has negative boundaries so deterministic edits and unsupported precision do not trigger a probabilistic workflow.

## Use cases

For a SaaS startup, Pearl can help investigate questions like these using models and assumptions you supply:

- Financial: “Will cash last until the next fundraise?” “Can we afford two hires if sales slip?” “Is an annual-prepayment discount worth offering?” Compare scenarios with uncertain revenue, churn, and payment timing rather than relying on one optimistic budget.
- Product and growth: “Would higher prices outweigh increased churn?” “Did onboarding changes cause better activation?” “Is one enterprise customer's custom feature worth delaying the roadmap?” Compare uncertain payoffs and make causal assumptions explicit rather than treating correlation as proof.
- Engineering: “Is this intermittent failure caused by our deploy, overload, or a provider?” “Should we rewrite or migrate incrementally?” “Is another week of testing worth delaying launch?” Track competing explanations, weigh downside risk, and decide which diagnostic test or prototype is worth doing next.
- Resources and delivery: “How many workers do we need before queues back up?” “Should we hire another support agent or improve self-service?” “How likely are we to finish a migration before the contractual deadline?” Use single-queue simulations and simple duration calculations to explore bottlenecks and deadline risks.

The durable record lets you revisit a decision as evidence changes without losing the original assumptions. See [expanded SaaS use cases](USE_CASES.md) for more context on each scenario and the limits of the models.

## Claude Desktop Chat

For ordinary Desktop Chat, install the Pearl skills from this Git marketplace URL after the changes are pushed:

```text
https://github.com/anateus/pearl-of-wisdom.git
```

The repository is private. Use an authenticated import or an organization-managed marketplace, or upload `pearl-of-wisdom-0.4.0.plugin` through **Customize > Plugins** without repository access. Keep the repository private unless its owner approves a visibility change.

Install and enable the `pearl-of-wisdom` plugin, then install the companion `pearl-of-wisdom-0.4.0.mcpb` through **Settings > Extensions**. The plugin supplies reasoning instructions; the extension runs Pearl's Python locally through uv and exposes MCP tools. Marketplace skills alone do not launch local tools in Chat. Claude Code and Cowork are not required.

See the [Desktop installation guide](desktop/README.md) for permissions, first-start downloads, persistent SQLite storage, a manual Developer fallback, and bundle builds. Model responses still use your Claude account: local computation does not keep tool results out of the conversation.

## Python CLI setup

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required for the standalone CLI.

```bash
uv sync --locked
uv run pearl-of-wisdom --help
```

Commands write compact JSON to standard output, except for the text help and `--version` output. Errors are JSON on standard error with a stable error code. `--db PATH` takes precedence over `PEARL_DB`; the default is `pearl.sqlite3`.

## A quick analysis

`analyze` runs without opening a database:

```bash
uv run pearl-of-wisdom analyze --engine monte-carlo --data '{
  "variables": {
    "price": {"distribution": "constant", "value": 12.5},
    "units": {"distribution": "constant", "value": 8}
  },
  "expression": "price * units - 10",
  "samples": 5,
  "seed": 71,
  "quantiles": [0, 0.5, 1]
}'
```

Monte Carlo requests support `constant`, `normal`, `uniform`, `bernoulli`, `triangular`, `lognormal`, `randint`, and numeric `discrete` distributions. Sample counts must be between 1 and 1,000,000. Expressions allow bounded arithmetic over declared variable names and reject calls, attributes, comprehensions, exponentiation, unknown names, and non-finite results.

The same engine is available from Python:

```python
from pearl_of_wisdom.engines import MonteCarloEngine

result = MonteCarloEngine().analyze(
    {
        "variables": {
            "demand": {
                "distribution": "normal",
                "mean": 100,
                "standard_deviation": 8,
            }
        },
        "expression": "demand * 12",
        "samples": 1_000,
        "seed": 7,
    }
)
```

## Optional visualization

The separate [`pearl-of-wisdom-viz`](visualization) package turns Monte Carlo results into question-led reports for general readers, empirical cumulative distributions, and scenario interval comparisons. Pearl core still has no runtime dependencies.

Distribution rendering requires `return_draws: true`. Draw exports are capped at 10,000 aligned rows and 16 selected input columns, while every existing summary continues to use the complete run. Bokeh HTML is portable and offline by default; shared local resources, CDN resources, and optional Matplotlib PNG output are explicit choices.

An explanatory report starts with a question and conditional answer, then shows the outcome range, model arithmetic, assumptions, and limitations. Named threshold counts use every simulation, including outcomes omitted from a capped export. The report binds authored context to saved results with hashes; the author still owns the validity of the assumptions and units.

Try the synthetic project-deadline example from this checkout:

```bash
uv run --project visualization --with-editable . python visualization/examples/generate.py \
  --out-dir reports/project
```

Open `reports/project/project-deadline.html` and compare current scope with 20% less work. See the [worked examples](visualization/examples/README.md) for a budget question using the same renderer.

See the [visualization companion guide](visualization/README.md) for installation, commands, resource ownership, and artifact lifecycle details.

## A durable investigation

New investigations are ephemeral by default. Record the useful parts as the work develops, then promote the investigation when it is worth keeping.

```bash
uv run pearl-of-wisdom --db pearl.sqlite3 create
uv run pearl-of-wisdom --db pearl.sqlite3 record-context INV_ID \
  --data '{"question":"Will this rollout pay off?"}'
uv run pearl-of-wisdom --db pearl.sqlite3 record-assumption INV_ID \
  --data '{"name":"traffic","value":"stable"}'
uv run pearl-of-wisdom --db pearl.sqlite3 record-evidence INV_ID \
  --data '{"source":"experiment","conversion_delta":0.03}'
uv run pearl-of-wisdom --db pearl.sqlite3 record-analysis INV_ID \
  --engine monte-carlo --data '{"summary":"paste the analyzed result here"}'
uv run pearl-of-wisdom --db pearl.sqlite3 promote INV_ID
uv run pearl-of-wisdom --db pearl.sqlite3 show INV_ID
```

`record-analysis` accepts a recorded result from any engine. It does not rerun that engine. This keeps execution and persistence separate for the first release.

## Discrete Bayes

`DiscreteBayesEngine` accepts finite variables, their parent lists, complete conditional probability tables, a query, and optional evidence:

```python
from pearl_of_wisdom.engines import DiscreteBayesEngine

result = DiscreteBayesEngine().analyze(
    {
        "network": {
            "variables": {
                "rain": {
                    "states": ["yes", "no"],
                    "parents": [],
                    "cpt": [{"when": {}, "probabilities": {"yes": 0.2, "no": 0.8}}],
                },
                "wet": {
                    "states": ["yes", "no"],
                    "parents": ["rain"],
                    "cpt": [
                        {
                            "when": {"rain": "yes"},
                            "probabilities": {"yes": 0.9, "no": 0.1},
                        },
                        {
                            "when": {"rain": "no"},
                            "probabilities": {"yes": 0.1, "no": 0.9},
                        },
                    ],
                },
            }
        },
        "query": ["rain"],
        "evidence": {"wet": "yes"},
    }
)
```

The engine validates cycles, states, table coverage, normalization, impossible evidence, and state-space size. Its default limit is 4,096 joint states. `discrete-bayes` performs observational inference. Use the separate `causal` engine for interventions under explicit causal assumptions.

## Decision analysis and value of information

`decision-analysis` takes state probabilities, actions with per-state utilities, and optional tests with observation likelihoods and costs. It reports expected utilities, all optimal actions, regret, expected value of perfect information (`evpi`), and each test's gross and net expected value of sample information (`evsi`, `net_evsi`). Test costs use the same utility scale as the action payoffs.

```bash
uv run pearl-of-wisdom analyze --engine decision-analysis --data '{
  "states": {"good": 0.4, "bad": 0.6},
  "actions": {
    "launch": {"good": 100, "bad": -40},
    "wait": {"good": 0, "bad": 0}
  },
  "tests": {
    "pilot": {
      "cost": 2,
      "likelihoods": {
        "good": {"positive": 0.8, "negative": 0.2},
        "bad": {"positive": 0.2, "negative": 0.8}
      }
    }
  }
}'
```

These illustrative inputs make `launch` optimal at expected utility 16. Perfect information is worth 24 utility units; the pilot is worth 11.2 before its cost and 9.2 after it. Each test is evaluated independently as an alternative to acting now. The engine does not optimize sequences of experiments. See the [decision-analysis reference](plugins/pearl-of-wisdom/skills/reasoning-under-uncertainty/references/decision-analysis.md) for the request and output rules.

## Causal interventions

`causal` reuses the discrete network format and requires `interventions`, `query`, and a nonempty list of `assumptions`. It validates the original network, replaces the intervened variables' mechanisms, then calculates the query distribution. Optional `evidence` conditions on the resulting intervened model.

```bash
uv run pearl-of-wisdom analyze --engine causal --example
```

An intervention can change the result even when the same variable and value appear in observational evidence. The engine calculates effects under the supplied causal model; it does not establish that the graph is correct, discover confounders, or identify effects from arbitrary datasets. Its default state-space limit is 4,096 joint states. The [causal reference](plugins/pearl-of-wisdom/skills/reasoning-under-uncertainty/references/causal.md) explains the assumptions and evidence semantics.

## System simulation

`system-simulation` models one FIFO queue feeding a fixed number of workers. It accepts a fixed arrival schedule or a finite sampled arrival process, fixed or sampled service times, optional waiting capacity and timeout, and failures with bounded retries. A simulated clock advances through events until the horizon; no daemon is involved.

```bash
uv run pearl-of-wisdom analyze --engine system-simulation --data '{
  "arrivals": {"times": [0, 1, 2]},
  "service_time": 3,
  "servers": 1,
  "horizon": 10,
  "seed": 7
}'
```

This queue completes three jobs with response times 3, 5, and 7 time units. The worker is busy for 9 of the 10 time units. Results include throughput, delay, time-average queue length, utilization, and unfinished work. The [simulation reference](plugins/pearl-of-wisdom/skills/reasoning-under-uncertainty/references/system-simulation.md) defines the measurement window, event ordering, limits, and supported distributions. General networks of queues and arbitrary process scripts are outside this engine's scope.

## Codex and Claude skills

[plugins/pearl-of-wisdom](plugins/pearl-of-wisdom) is one self-contained plugin tree. Both manifests point to the same skills, and both hosts discover the shared hook file. This follows the useful part of Hindsight's unified approach: shared behavior with thin host-specific packaging.

Claude Code can install the plugin from the same marketplace:

```text
/plugin install pearl-of-wisdom --marketplace anateus/pearl-of-wisdom
```

For a checkout-only session, Claude Code can load it directly:

```bash
claude --plugin-dir "$PWD/plugins/pearl-of-wisdom"
```

Codex loads the same tree after it is installed from a configured local marketplace. This repository does not modify a user's marketplace. Add the plugin with Codex's `$plugin-creator` skill, then review and trust its bundled hook when Codex prompts. Codex discovers `hooks/hooks.json` from the plugin root and provides the same plugin-root environment variable used by Claude.

The `UserPromptSubmit` hook is advisory and fail-open. It emits a short suggestion for likely uncertainty or investigation prompts, stays silent for ordinary edits, never runs an analysis, and does not log raw prompts. Routing fixtures live in [plugins/pearl-of-wisdom/evals](plugins/pearl-of-wisdom/evals).

Hindsight is optional. If it is present, the skills may use it for continuity. Recalled memory is context, never an observation, prior, or likelihood in an investigation.

The plugin uses a one-time installation of its Python CLI. From this checkout:

```bash
uv tool install --reinstall ./plugins/pearl-of-wisdom/cli/pearl_of_wisdom-0.4.0-py3-none-any.whl
python3 ./plugins/pearl-of-wisdom/scripts/check_cli.py
```

The [compatibility check](plugins/pearl-of-wisdom/scripts/check_cli.py) accepts CLI versions `>=0.4.0,<0.5.0` and returns the installed executable's absolute path. Missing, older, newer-minor, and unrecognized versions stop the workflow with an exact install command for this plugin's wheel. The check reads the required version from the plugin manifest; later stable patches in the same minor release are compatible.

Without MCP tools, Code and Codex skills run the installed executable directly after this check. Normal CLI use needs Python and access to the investigation database, without writable uv caches or tool directories. `uv` is needed for installation and updates. If the host requires approval to write its tool directories, approve that install command or run it in a terminal, then rerun the check. Installation does not change later commands' sandbox permissions. Python 3 must be available as `python3` for the plugin check and hook.

## Host end-to-end tests

Host tests are opt-in because they install or load the plugin and make real model requests. Run them through `uv` to provide the test dependencies:

```bash
PEARL_RUN_HOST_E2E=1 uv run pytest -q tests/e2e/test_codex_host.py
PEARL_RUN_HOST_E2E=1 uv run pytest -q tests/e2e/test_claude_host.py
```

The Codex test creates a temporary local marketplace and `CODEX_HOME`, installs the checkout with `codex plugin add`, and confirms that Codex lists it as installed and enabled. It runs positive, negative, and ambiguous prompts in fresh sessions. The positive case must load the routing skill, while the negative case must leave both Pearl skills unused. The test installs the bundled wheel into a temporary tool environment and removes other Pearl executables from the session PATH. A fourth session loads the durable-investigation skill, runs its compatibility check, creates a SQLite investigation through the installed CLI, and records context under workspace-write permissions. The session cannot invoke uv through PATH, and the test rejects attempts to run a package installer. The test reads that record directly through the CLI, removes the plugin, and confirms that it is no longer installed. Authentication material is copied only into pytest's temporary directory with user-only permissions.

The Claude test loads the checkout for two fresh sessions with `--plugin-dir`. The positive session must invoke the installed routing skill through Claude's `Skill` tool. The negative session may use unrelated host skills, but it must not invoke either Pearl skill. The test also checks the host debug stream for the real `UserPromptSubmit` advisory on the positive prompt and confirms that the same advisory is absent on the negative prompt. Empty setting sources and a strict empty MCP configuration keep caller customizations out of both sessions. `--no-session-persistence` prevents either session from entering Claude's history.

Both tests skip when `PEARL_RUN_HOST_E2E` is unset or the required host CLI is missing. Missing authentication also skips with a specific reason. Model failures and timeouts fail the test. These tests use the configured host accounts and may consume paid model usage. A run containing only skips does not prove host behavior; check the pytest summary for executed tests.

## What is deferred

There is no daemon in this release. Direct CLI calls avoid another lifecycle and protocol while startup cost is negligible. A local daemon becomes useful if measurements show repeated startup cost, concurrent clients, subscriptions, or coordination needs.

Dependent Monte Carlo inputs, schema migrations, and automatic engine-result persistence remain deferred. Record results from any engine with `record-analysis` when they need to be kept. Causal discovery, general causal estimation from datasets, sequential experiment optimization, and general networks of queues are also outside the current engine scope.

## Development

The full test suite builds and launches the actual Desktop extension. Node.js/npm are required for the pinned MCPB validator and packer, in addition to Python and uv. These checks use synthetic inputs, not a Claude Desktop model session.

```bash
uv run pytest -q
uv run ruff check .
uv build
claude plugin validate --strict plugins/pearl-of-wisdom
PEARL_RUN_HOST_E2E=1 uv run pytest -q tests/e2e
```

Codex and skill validation use the scripts shipped with Codex's `plugin-creator` and `skill-creator` skills. See the test suite for the host-neutral contract checks and hook smoke cases.
