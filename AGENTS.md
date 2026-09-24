# AI Agent Rules

Read this file before changing code, tests, build files, documentation, or planning artifacts.

## Source of truth

- `AGENTS.md`: stable repository-wide agent rules.
- GitHub Issues: live project context, decisions, status, milestones, hierarchy, dependencies, release gates, and artifact pointers.
- `CONTEXT.md`: canonical domain language.
- `docs/adr/`: hard-to-reverse architecture decisions.
- `docs/research/`: research evidence.
- `docs/guardrails/`: machine-discoverable design guardrails when present.
- Code, tests, and build files: implementation truth.

Do not treat chat history as project truth. If canonical sources conflict, report the drift in the active Issue and resolve it before continuing.

## Cold start

Use `gh` as the default project interface. Do not guess the active work from recent chat, branch names, or the oldest open Issue.

First locate the single open current context:

```bash
gh issue list -R OWNER/REPO \
  --label work:current --state open \
  --json number,title,labels,milestone,url
```

The result must contain exactly one Issue during normal work. During implementation/dogfood, that Issue must be an `execution:epic`; during planning it is the active planning context. `0` or more than `1` current contexts is an invariant failure: stop and report it rather than selecting work heuristically.

When the repository commands are available, use:

```bash
just frontier
just next
```

`frontier` means open + unblocked + unclaimed claimable leaf work under the sole current context. During execution, claimable leaves are `execution:task` descendants. Priority order is `priority:P0`, then `priority:P1`, then `priority:P2`; lower Issue number breaks ties. Missing/multiple priority labels are invalid metadata, not defaults. `just next` selects but never claims work.

Claim a selected leaf by assigning it before changing repository artifacts.

For manual inspection or diagnosis:

```bash
gh issue view ISSUE -R OWNER/REPO --comments \
  --json number,title,body,state,stateReason,labels,milestone,parent,subIssues,blockedBy,blocking,assignees,comments,url

gh api repos/OWNER/REPO/contents/CONTEXT.md \
  -H 'Accept: application/vnd.github.raw+json'
```

Native GitHub milestone, hierarchy, dependency, label, assignee, and state metadata are canonical whenever the active tracker/dev environment exposes the required operations. A Markdown/body relationship graph is compatibility-only when native mutation is unavailable. If a current context declares such a fallback, surface that degraded tracker mode explicitly; do not silently compute a supposedly canonical frontier from an incomplete native graph.

Follow Issue pointers to ADRs, research, and guardrails only when needed. For guardrail-relevant work, start at `docs/guardrails/registry.yaml`, load active records matching the scope or triggers, then follow their canonical source pointers.

A zero-context agent must be able to answer from tracker/repository state alone: what is current, what work is available, what is blocked, what should be taken first, how to claim it, what canonical decisions constrain it, and how completion is proved.

## Working rules

- Work from an explicit GitHub Issue for planned work.
- Check dependencies before starting; claim an unassigned frontier Issue before working it.
- Keep changes small and vertical around an observable outcome, not a technical layer.
- Use domain terms from `CONTEXT.md`; do not invent competing vocabulary.
- Do not introduce new process boundaries, helpers, IPC, HID takeover, or other hard-to-reverse architecture changes without a decision Issue and ADR.
- Update the active Issue when a material fact or decision changes what later agents need to know.
- External products and codebases are reference implementations and research inputs. Use them to reduce rediscovery: identify the smallest known-good pattern, adapt it to this repository's established boundaries and domain language, then verify the observable behavior through an established seam or on the permitted reference Mac. `/Users/cuongpham/Projects/repo-x` is an optional local reference input only: if absent, continue without hunting for it.
- Do not copy or mechanically transform external code, comments, documentation prose, tests, distinctive naming, module structure, control flow, or product expression. Reuse ideas and behavior, not expression.
- Default delivery route for a precedent-backed change: reference observation → minimal adaptation → targeted verification → ship. Independent research, a new decision Issue, or a prototype is not required merely because the precedent came from an external codebase.
- Do not block implementation to prove speculative implementation details. If uncertainty does not affect observable behavior, fail-open/safety guarantees, an established public boundary, or a hard-to-reverse decision, choose the simplest known-good pattern and continue.
- Enter a deep-research/decision path only when at least one trigger is present: the solution depends on undocumented/private behavior; the reference conflicts with current repository contracts; the behavior fails on the permitted reference Mac; the change alters a hard-to-reverse architecture/public ABI/persistence contract; or existing public seams cannot bound a material fail-open, safety, or hot-path risk.
- A reference-derived value or internal detail must not become a test oracle merely by being copied from the reference. Prefer an independently observable behavior, public documentation when needed, or a minimal local probe only for the specific deep-path uncertainty.
- Timebox exploratory research for normal implementation work. If no deep-path trigger is found within 30 minutes, stop researching and implement the smallest vertical change supported by the best available precedent and current repository contracts.
- When asking or consulting Oracle for second-model review, architecture feedback, or design validation, always use the dedicated ChatGPT project: `https://chatgpt.com/g/g-p-6a8825fba8a88191b61159104f8bf9f8-mac-mouse-flow/project` (e.g., passing `--chatgpt-url https://chatgpt.com/g/g-p-6a8825fba8a88191b61159104f8bf9f8-mac-mouse-flow/project` to Oracle). Treat responses as advisory and independently verify them against the codebase and tests.

## M0 + v0.1 architecture guardrails

Until superseded by a later decision:

- One SwiftUI/AppKit process with a native input adapter and a platform-neutral Rust engine.
- Swift/AppKit owns macOS lifecycle, permissions, `CGEventTap`, native event extraction/application, and platform I/O outside the input callback.
- Rust owns platform-neutral normalization, domain semantics, configuration evaluation, and `Input Decision`.
- Swift ↔ Rust uses a narrow manual C ABI with fixed-layout values on the hot path.
- The input callback must not perform UI/MainActor work, disk or network I/O, synchronous logging, config parsing, or unbounded blocking/locking.
- Bridge or engine failure must fail open and preserve the original input.
- Never infer physical `Device Identity` from `Scroll Granularity`, timestamps, or undocumented correlation.
- v0.1 transforms `LineBased` scroll only; `PixelBased` scroll is preserved by default.

## Delivery paths

Use the fast path by default for a small or medium Issue with an established architecture and a known implementation precedent:

1. Claim the Issue and read only its direct canonical pointers.
2. Inspect the existing code plus the closest relevant reference pattern.
3. Implement the smallest vertical change that produces the observable outcome.
4. Run the smallest relevant public-seam test or canonical command.
5. For native input behavior, smoke-test the observable result on the permitted reference Mac.
6. Stop when the Issue acceptance is met. Do not add compatibility, abstractions, diagnostics, benchmarks, documentation, or tests that the Issue does not require.

Use the deep path only when one of the deep-path triggers above is present. Wayfinder, prototype, domain-modeling, broad research, and additional architecture work are escalation tools, not mandatory ceremony for every Issue.

For current pre-v1 work, the permitted Apple-silicon reference Mac is the primary product compatibility target unless the active Issue explicitly requires broader compatibility. Do not expand implementation or verification to Intel, universal binaries, extra macOS/Xcode matrices, or generic portability without an Issue requirement.

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

Git hooks and GitHub Actions must call canonical commands instead of duplicating verification logic. Hooks are feedback gates, not final acceptance gates.

Establish the GitHub Actions workflow and observe its required status check passing before making that check mandatory in a repository ruleset/branch-protection policy. Required workflow behavior must not disappear for docs-only changes because of a top-level path filter.

Test behavior through established public seams. If a test would require inventing a new interface/trait/protocol/adapter/provider/gateway/repository/mock/fake solely for testability, stop production TDD and resolve the boundary first. Mock or fake only at established system boundaries.

Strict latency evidence comes from the reference Mac, not hosted CI timing. Hot-path diagnostics must use bounded enqueue/buffering only; prefer dropping trace data over blocking input.

## Wayfinder planning

- During planning, discover the active context through `work:current`; the strategic Road-to-v1 map is not current execution work.
- The `wayfinder:map` label identifies planning maps, but it is not the universal cold-start selector.
- Decision details live in resolution comments, not duplicated in the map.
- Milestones represent releases; labels represent work type; parent/sub-issue represents decomposition; blocked-by/blocking represents dependency.
- Prefer native GitHub relationships over Markdown dependency lists; body fallback is compatibility-only when native mutation is unavailable.
- Resolve at most one non-research Wayfinder ticket per planning session.

Keep this file short and stable. Do not copy transient milestones, frontier state, dependency graphs, Issue numbers, or full decision bodies into it.
