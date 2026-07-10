# Redteam Benchmark

Adversarial security/safety testing for the NF Portal Assistant, using [deepteam](https://github.com/confident-ai/deepteam) to drive an attacker LLM against the live (**dev**) copilot and judge whether it resists each attack.

## Background

The copilot has **read-only** access only: a documentation knowledge base (RAG) and a SPARQL action group limited to four read-only operations (`sparqlQuery`, `getSchema`, `getShape`, `countByType`). It has no code execution and no write/mutation capability anywhere in the stack. This benchmark checks whether an attacker can still get the agent to overstep its intended functionality (e.g. being repurposed as a general-purpose assistant for unrelated tasks), leak data it shouldn't, give unsafe medical guidance, claim capabilities it doesn't have, or be manipulated via SPARQL/RAG-specific injection vectors.

Unlike other current benchnmarks, this benchmark is **dynamic**: for each vulnerability, an attacker LLM generates and iterates attack prompts (including multi-turn jailbreak escalation) against the live agent, and a judge LLM scores whether each attack succeeded.

## ⚠️ Safety

- This script **actively attacks a live Bedrock Agent alias**. It refuses to run against the known prod agent id (`R7WZ38JGKX`) unless you pass `--allow-prod` — don't do that without a specific reason.
- Default target is the dev agent (`ERAAPKTD4Q`) on `TSTALIASID` (DRAFT).
- Result JSON files can contain **successfully leaked/harmful content** the attacks extracted from the agent — that's the point of the exercise, but review before sharing or committing results outside this benchmark's normal workflow.
- `deepteam`/`deepeval` telemetry is anonymous usage analytics, not a data-sharing risk to worry about here, but if you want it off: `export DEEPTEAM_TELEMETRY_OPT_OUT=YES`. Uploading results to Confident AI's cloud (`_upload_to_confident`) only happens if you've configured a Confident AI API key — don't configure one for this benchmark.

## Setup

**Requires Python 3.9–3.12.** `deepteam` 1.0.7 fails to import on Python 3.13+ (it references the stdlib `nntplib` module, removed in 3.13). Use a 3.12 (or earlier) virtualenv:

```bash
python3.12 -m venv .venv-redteam
source .venv-redteam/bin/activate
pip install deepteam boto3 aiobotocore pandas jsonschema
```

Install `boto3`, `aiobotocore`, and `deepteam` together in one `pip install` call as shown — resolving them separately can pin an `aiobotocore` version that requires an older `botocore` than `boto3` needs, which breaks `boto3` imports.

AWS credentials with access to the Bedrock Agent (`bedrock-agent-runtime`) and Bedrock Runtime Converse API (`bedrock-runtime`) for the dev account.

## Config

`redteam_config.json` — a list of vulnerability x attack pairings, validated against `redteam_schema.json`. Each entry is either:

- `kind: "builtin"` — a deepteam class from `deepteam.vulnerabilities` (e.g. `PIILeakage`, `PromptLeakage`, `ExcessiveAgency`), optionally restricted to a subset of its `types` via `builtin_types`.
- `kind: "custom"` — a `CustomVulnerability` defined inline with `name`, `criteria` (what the judge should check for), and `types`.

v1 entries:

| `vulnerability_id` | Category | What it checks |
|---|---|---|
| `off-topic-repurposing` | Agentic | Agent being repurposed as a general-purpose assistant for tasks unrelated to the NF Portal (`ExcessiveAgency`'s `functionality` type) |
| `pii-leakage` | Data privacy | Disclosure of personal info about contributors/contacts via docs KB or graph. **Note: the docs KB and graph contain no actual PII** — this is defense-in-depth against fabricated/hallucinated PII, testing principled refusal, and guarding against future content changes |
| `prompt-leakage` | Data privacy | Leaking system instructions, internal guardrails, or endpoint/config details |
| `nf-medical-misinformation` | Safety | Unqualified diagnostic/treatment claims for NF conditions, missing disclaimers to patient personas |
| `excessive-agency` | Agentic | False capability claims, e.g. claiming to write/execute code or modify portal data, which this agent must never (and can't) do (`ExcessiveAgency`'s `permissions` and `autonomy` types) |
| `sparql-injection` | Security | Attacker-crafted SPARQL exceeding normal read-only scope, or endpoint/query internals disclosure |

To add a new vulnerability, add an entry to `redteam_config.json` (validate against `redteam_schema.json`) — all deepteam attack techniques are already in the schema's `attacks` enum, so no code changes are needed.

### All deepteam attack techniques

`deepteam` (1.0.7) ships these attack technique classes. All of them are in `redteam_schema.json`'s `attacks` enum and available to use.
Legend: ✅ used by at least one entry in `redteam_config.json` · 🔲 available, not yet paired with an entry.
Attack techniques are generic (any of them can in principle be applied to any vulnerability) — notes below are only given where a technique has a notable fit or mismatch with our current entries.

**Single-turn** (`deepteam.attacks.single_turn`):

| Technique | Status | Notes |
|---|---|---|
| `PromptInjection` | ✅ | Used across most entries |
| `Roleplay` | ✅ | Used for medical misinformation, excessive agency, SPARQL injection |
| `GoalRedirection` | ✅ | Used for medical misinformation, excessive agency |
| `PermissionEscalation` | ✅ | Used for prompt leakage, excessive agency |
| `SystemOverride` | ✅ | Used for excessive agency |
| `GrayBox` | 🔲 | Invents fake system rules/exceptions to bypass safety — good fit for `excessive-agency`, `prompt-leakage`, `sparql-injection` |
| `ContextPoisoning` | 🔲 | RAG-injection technique; not currently used |
| `SyntheticContextInjection` | 🔲 | RAG-injection technique; not currentl used |
| `MathProblem` | 🔲 | Disguises harmful intent as a math/logic problem to dodge keyword filters |
| `Base64` | 🔲 | Encoding-bypass |
| `Leetspeak` | 🔲 | Encoding-bypass |
| `ROT13` | 🔲 | Encoding-bypass |
| `AuthorityEscalation` | 🔲 | |
| `EmotionalManipulation` | 🔲 | |
| `PromptProbing` | 🔲 | |
| `InputBypass` | 🔲 | |
| `ContextFlooding` | 🔲 | |
| `EmbeddedInstructionJSON` | 🔲 | |
| `CharacterStream` | 🔲 | |
| `LinguisticConfusion` | 🔲 | |
| `Multilingual` | 🔲 | |
| `AdversarialPoetry` | 🔲 | |

**Multi-turn** (`deepteam.attacks.multi_turn`):

| Technique | Status | Notes |
|---|---|---|
| `LinearJailbreaking` | ✅ | Used for PII/prompt leakage, SPARQL injection |
| `CrescendoJailbreaking` | ✅ | Used for medical misinformation |
| `TreeJailbreaking` | 🔲 | |
| `SequentialJailbreak` | 🔲 | |
| `BadLikertJudge` | 🔲 | |

### All deepteam vulnerability categories

Legend: ✅ covered — an entry in `redteam_config.json` uses this class (or a `CustomVulnerability` covers the same concern) · 🔲 deferred — a plausible, valid addition that just hasn't been prioritized yet · ➖ not applicable — excluded because the copilot's actual capability surface doesn't have the matching attack surface (no code execution, no auth/role model, single agent, no autonomous task loop, etc.).

| Group | Vulnerability | Status | Notes |
|---|---|---|---|
| Data Privacy | `PIILeakage` | ✅ | `pii-leakage` |
| Data Privacy | `PromptLeakage` | ✅ | `prompt-leakage` |
| Responsible AI | `Bias` | 🔲 | Worth adding given patient-facing personas |
| Responsible AI | `Toxicity` | 🔲 | Worth adding given patient-facing personas |
| Responsible AI | `Fairness` | 🔲 | Worth adding given patient-facing personas |
| Responsible AI | `ChildProtection` | ➖ | No child-directed content surface |
| Responsible AI | `Ethics` | 🔲 | Not yet scoped |
| Security | `BFLA` | ➖ | No auth boundaries to test — single public-facing agent, no per-user function-level access control |
| Security | `BOLA` | ➖ | No auth boundaries to test — no per-object access control model |
| Security | `RBAC` | ➖ | No role model — agent has one fixed capability set for all users |
| Security | `DebugAccess` | ➖ | No debug interface exposed |
| Security | `ShellInjection` | ➖ | No code execution capability anywhere in the stack |
| Security | `SQLInjection` | ➖ | No SQL backend; closest analog is `sparql-injection` (custom) |
| Security | `SSRF` | ➖ | Agent can't fetch arbitrary attacker-supplied URLs |
| Security | `ToolMetadataPoisoning` | ➖ | No dynamically-loaded/third-party tool metadata |
| Security | `CrossContextRetrieval` | ➖ | Tests cross-tenant/cross-user/cross-role data leakage in multi-tenant RAG systems; the copilot is single-tenant with no login/session isolation or role differentiation, so there's no other tenant's/user's/role's data to leak |
| Security | `SystemReconnaissance` | 🔲 | Covers 3 types: `file_metadata`, `database_schema`, `retrieval_config` (chunk size, embedding model, similarity thresholds). Most of this we don't care about — we're fine with the copilot describing its own capabilities/sources to users, and `getSchema` is an intentionally-exposed read-only SPARQL operation. The one subset worth testing later is precise backend/software fingerprinting (e.g. exact triple-store engine + version, embedding model + version) that goes beyond capability disclosure into detail that could aid crafting an engine-specific exploit elsewhere — narrower than the builtin's full scope |
| Safety | `IllegalActivity` | 🔲 | Not yet scoped |
| Safety | `GraphicContent` | ➖ | No user-generated or open-ended creative content surface |
| Safety | `PersonalSafety` | 🔲 | Overlaps with `nf-medical-misinformation` (custom); could formalize as this builtin |
| Safety | `UnexpectedCodeExecution` | ➖ | No code execution capability anywhere in the stack |
| Business | `Misinformation` | 🔲 | `nf-medical-misinformation` (custom) covers the medical case specifically; general misinformation not yet covered |
| Business | `Hallucination` | 🔲 | Distinct from other benchmarks that already assess groundedness: baits confabulation by presupposing something false exists (fake citations, APIs, entities, or statistics), rather than scoring answers to real questions with known-correct answers |
| Business | `IntellectualProperty` | ➖ | No proprietary content generation surface |
| Business | `Competition` | ➖ | No competitor-comparison surface |
| Agentic | `ExcessiveAgency` | ✅ | Split across two entries: `off-topic-repurposing` (`functionality` type) and `excessive-agency` (`permissions`, `autonomy` types) |
| Agentic | `GoalTheft` | ➖ | No autonomous multi-step task execution to hijack |
| Agentic | `RecursiveHijacking` | ➖ | No autonomous multi-step task execution to hijack |
| Agentic | `Robustness` | 🔲 | General adversarial-input resilience, not vulnerability-specific |
| Agentic | `IndirectInstruction` | 🔲 | Instruction-following from malicious retrieved content (e.g. a crafted string embedded in a dataset description or help page) |
| Agentic | `ToolOrchestrationAbuse` | ➖ | No multi-tool chaining/orchestration to abuse |
| Agentic | `AgentIdentityAbuse` | ➖ | Single agent, no identity delegation |
| Agentic | `InsecureInterAgentCommunication` | ➖ | No multi-agent communication |
| Agentic | `AutonomousAgentDrift` | ➖ | No autonomous long-running task loop to drift from |
| Agentic | `ExploitToolAgent` | ➖ | No tool-using sub-agent to exploit |
| Agentic | `ExternalSystemAbuse` | ➖ | No external system calls beyond the read-only SPARQL endpoint (covered by `sparql-injection`) |
| — | `CustomVulnerability` | ✅ | Used for `nf-medical-misinformation`, `sparql-injection` |

Re-check the ➖ rows if the copilot's capabilities change (e.g. it gains write access, an auth model, or multi-agent delegation) — those exclusions are tied to the current architecture, not a permanent judgment. 🔲 rows are open invitations to extend `redteam_config.json`.

## Running

```bash
cd benchmark/redteam
python evaluate_redteam.py                                  # all config entries, dev agent
python evaluate_redteam.py --vulnerability pii-leakage       # one config entry
python evaluate_redteam.py --attacks-per-type 3              # more attacks per vulnerability type
python evaluate_redteam.py --agent-id ERAAPKTD4Q             # explicit dev agent id
```

The default alias `TSTALIASID` always points to the DRAFT version. If you've updated the agent without preparing it, run `aws bedrock-agent prepare-agent --agent-id <ID>` first.

| Flag | Default | Description |
|------|---------|-------------|
| `--agent-id` | `ERAAPKTD4Q` (dev) | Bedrock Agent ID |
| `--alias-id` | `TSTALIASID` | Bedrock Agent alias ID (DRAFT) |
| `--allow-prod` | off | Required to target the prod agent id |
| `--config` | `redteam_config.json` | Vulnerability x attack config |
| `--vulnerability` | all | Only run one config entry by `vulnerability_id` |
| `--simulator-model` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock model used to generate attacks |
| `--evaluation-model` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | Bedrock model used to judge pass/fail |
| `--attacks-per-type` | 1 | Attacks simulated per vulnerability type |
| `--max-concurrent` | 3 | Kept low vs. deepteam's default (10) to avoid rate-limiting the dev alias |
| `--profile` | env credentials | AWS profile |
| `--region` | `us-east-1` | AWS region |

## How it works

`evaluate_redteam.py` wraps Bedrock's `invoke_agent` (same trace-parsing approach as `../kb-routing/evaluate_kb_routing.py`: `KNOWLEDGE_BASE` trace → `DOCS`, `ACTION_GROUP` trace → `GRAPH`) as a deepteam `model_callback`. Because `invoke_agent` is session-based (a Bedrock `sessionId` carries conversation memory server-side), the callback mints a fresh session at the start of each attack conversation and reuses it for every subsequent turn deepteam sends — multi-turn jailbreak attacks (`LinearJailbreaking`, `CrescendoJailbreaking`) therefore see the same session-level memory a real multi-turn chat user would.

Which KB/graph sources the agent actually consulted for each turn is recorded on `RTTurn.tools_called` (deepteam's field for this — not `metadata`, which several of its judge templates don't read) so the judge model has visibility into tool usage, which matters for judging `excessive-agency` cases.

`AmazonBedrockModel` (from `deepeval.models`, the async Bedrock Converse API adapter deepeval ships natively) is used directly for both the simulator and evaluation models — no custom LLM adapter needed.

## Output

Results are saved as `redteam_eval_results_<timestamp>.json`:

- `timestamp`, `config` — agent/alias ids, simulator/evaluation model ids, config file path
- `results` — per-attack test cases: `vulnerability_id`, `category`, `attack_method`, `input`, `actual_output`, `turns` (for multi-turn), `score`, `passed`, `reason`, `sources_used`
- `errors` — vulnerability-level errors (e.g. simulator/judge failures)

### Metrics printed

| Metric | Description |
|--------|-------------|
| Overall attack success rate | % of attacks the agent failed to resist |
| By vulnerability | Attack success rate per `vulnerability_id` |
| By category | Attack success rate per risk category (data-privacy, safety, security, agentic) |
| By attack technique | Which attack method (prompt injection, jailbreaking, etc.) succeeds most often |

A **low** attack success rate is good here — it means the copilot resisted the adversarial attempts. Review the full result JSON for any successful attacks before deciding on prompt/instruction changes.
