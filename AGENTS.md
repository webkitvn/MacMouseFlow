# AI Agent Rules

Read this file before changing code, tests, build files, documentation, or planning artifacts.

## Source of truth

Use sources by responsibility:

- `AGENTS.md`: stable repository-wide workflow rules.
- GitHub Issues: current work, decisions, milestones, hierarchy, dependencies, release gates, and artifact pointers.
- `CONTEXT.md`: canonical domain language.
- `docs/adr/`: hard-to-reverse architecture decisions.
- `docs/research/`: research evidence.
- `docs/guardrails/registry.yaml`: canonical entry point for active design guardrails.
- Code, tests, and build files: implementation truth.

Do not treat chat history as project truth. If canonical sources conflict, report the drift in the active Issue and resolve only the material conflict before continuing.

## Tools

Use the smallest tool that can resolve the current task.

- GitHub and `gh`: canonical interface for Issues, milestones, relationships, dependencies, claiming, and work status.
- `just frontier`: show open, unblocked, unclaimed claimable work under the current context.
- `just next`: select the highest-priority frontier Issue; never claims it.
- `CONTEXT.md`: resolve canonical domain terminology.
- ADRs: record hard-to-reverse or surprising architecture decisions.
- Research: resolve material uncertainty that cannot be answered from current code, contracts, or reliable precedent.
- Reference implementations: reduce rediscovery; adapt known-good behavior without copying external expression.
- Wayfinder: planning escalation for large, vague, cross-cutting, or roadmap work; not routine implementation.
- Domain modeling: use when domain semantics or boundaries are genuinely unclear.
- Prototype: use for unresolved feasibility; prototypes are disposable evidence, not production foundations.
- TDD, tests, and mocking: use established public seams; mock only established system boundaries. Do not invent production abstractions solely for testability.

### Oracle

Use Oracle only for material second-model review, architecture/design uncertainty, or an explicit review requirement. Treat its output as advisory and verify material conclusions against repository evidence and tests.

Always use ChatGPT through the browser engine with manual login and the dedicated project. Do not let Oracle auto-select API mode.

Canonical invocation:

```bash
oracle \
  --engine browser \
  --browser-manual-login \
  --chatgpt-url "https://chatgpt.com/g/g-p-6a8825fba8a88191b61159104f8bf9f8-mac-mouse-flow/project" \
  -p "<prompt>" \
  --file "<relevant-file>"
```

For first login or login recovery, keep the browser open:

```bash
oracle \
  --engine browser \
  --browser-manual-login \
  --browser-keep-browser \
  --chatgpt-url "https://chatgpt.com/g/g-p-6a8825fba8a88191b61159104f8bf9f8-mac-mouse-flow/project" \
  -p "Confirm the project session is available."
```

Oracle opens Chrome with its persistent manual-login profile. Log into ChatGPT manually in that window when required. Subsequent runs reuse that profile until the session expires.

Do not switch to API mode, cookie-copy mode, another ChatGPT project, or a different browser-session strategy unless the active Issue explicitly requires it.

## Start work

Use `gh` as the default project interface.

There must be exactly one open `work:current` context during normal work. During implementation or dogfood it must be the current execution context; during planning it is the current planning context. If none or multiple exist, stop and report the tracker inconsistency.

Use:

```text
just frontier
just next
```

Claim the selected Issue by assigning it before changing repository artifacts.

Work from an explicit GitHub Issue for planned work. Check its dependencies, acceptance criteria, declared target environment, and direct pointers before expanding context.

Native GitHub milestone, parent/sub-issue, blocked-by/blocking, labels, assignees, and state are canonical when supported. Use Markdown/body relationship fallback only when native mutation is unavailable.

For direct canonical-domain lookup through GitHub, use:

```bash
gh api repos/OWNER/REPO/contents/CONTEXT.md -H 'Accept: application/vnd.github.raw+json'
```

Follow pointers to ADRs, research, and guardrails only when relevant to the active work. For guardrail-relevant work, start at `docs/guardrails/registry.yaml`.

## Delivery

Keep changes small and vertical around an observable outcome.

Prefer the fast path:

`claim → inspect direct context and precedent → minimal adaptation → targeted verification → target-environment smoke when needed → ship`

Stop when the Issue acceptance criteria are met. Do not add compatibility work, abstractions, diagnostics, benchmarks, documentation, or tests that the Issue does not require.

Use reference implementations to reduce rediscovery. Reuse ideas and observable behavior, not code expression. Do not copy or mechanically transform external code, comments, documentation, tests, distinctive naming, module structure, or control flow.

Do not block implementation to prove speculative details.

Enter the deep path only when uncertainty materially involves one or more of:

- undocumented or private platform behavior;
- conflict with an established repository contract;
- failure in the active Issue's target environment;
- a hard-to-reverse architecture, ABI, persistence, or process-boundary decision;
- material fail-open, safety, correctness, or hot-path risk that existing seams cannot bound.

Wayfinder, research, prototype, domain modeling, and additional architecture work are escalation tools, not mandatory ceremony.

Timebox exploratory research for normal implementation work. If no deep-path trigger appears within 30 minutes, use the simplest reversible approach supported by current contracts and the best available precedent.

Use the compatibility target declared by the active Issue. Do not expand support to additional architectures, OS versions, toolchains, or compatibility matrices without an explicit requirement or demonstrated production failure.

Use domain terms from `CONTEXT.md`. Do not invent competing vocabulary.

Update the active Issue only when a material fact or decision changes what later agents need to know.

## Architecture guardrails

These are stable defaults unless explicitly superseded by a newer Issue decision, ADR, or active guardrail.

- Use one SwiftUI/AppKit process with a native input adapter and platform-neutral Rust engine.
- Swift/AppKit owns macOS lifecycle, permissions, `CGEventTap`, native event extraction/application, and platform I/O outside the input callback.
- Rust owns platform-neutral normalization, domain semantics, configuration evaluation, and `Input Decision`.
- Swift ↔ Rust uses a narrow manual C ABI with fixed-layout hot-path values.
- The input callback must not perform UI/MainActor work, disk/network I/O, synchronous logging, config parsing, or unbounded blocking/locking.
- Bridge or engine failure must fail open and preserve original input.
- Never infer physical `Device Identity` from `Scroll Granularity`, timestamps, or undocumented correlation.
- Do not introduce new process boundaries, IPC, HID takeover, or similarly hard-to-reverse architecture without an explicit decision and ADR.

## Verification

Canonical commands are the single source of verification behavior:

```text
just check
just test
just ci
just benchmark
just smoke
just hooks-install
just frontier
just next
```

Git hooks and GitHub Actions must call canonical commands instead of duplicating their logic.

Use the smallest verification set that proves the active Issue's acceptance criteria.

Test through established public seams. If a test requires a new production interface, trait, protocol, adapter, provider, gateway, repository, mock, or fake solely for testability, stop TDD and resolve the boundary first.

Strict latency evidence must come from the target/reference environment declared by the active Issue, not unrelated hosted CI timing.

Hot-path diagnostics must use bounded enqueue/buffering; prefer dropping diagnostic data over blocking input.

## Planning

Discover planning context through `work:current`. Strategic maps are not current execution work unless explicitly marked current.

Milestones represent releases. Labels represent work type. Parent/sub-issue represents decomposition. Blocked-by/blocking represents dependencies.

Prefer native GitHub relationships. Use body fallback only when the tracker cannot represent the relationship natively.

Keep decision details in their resolution comments or canonical artifacts instead of duplicating them into planning maps.

Resolve at most one non-research Wayfinder ticket per planning session.

Keep this file short and stable. Store workflow invariants and tool routing here; keep release-specific scope, compatibility matrices, frontier state, dependency graphs, Issue numbers, and full decision bodies in their canonical locations.
