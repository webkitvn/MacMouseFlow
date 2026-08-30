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

Follow Issue pointers to ADRs, research, and guardrails only when needed.

A zero-context agent must be able to answer from tracker/repository state alone: what is current, what work is available, what is blocked, what should be taken first, how to claim it, what canonical decisions constrain it, and how completion is proved.

## Working rules

- Work from an explicit GitHub Issue for planned work.
- Check dependencies before starting; claim an unassigned frontier Issue before working it.
- Keep changes small and vertical around an observable outcome, not a technical layer.
- Use domain terms from `CONTEXT.md`; do not invent competing vocabulary.
- Do not introduce new process boundaries, helpers, IPC, HID takeover, or other hard-to-reverse architecture changes without a decision Issue and ADR.
- Update the active Issue when a material fact or decision changes what later agents need to know.
- External products and codebases are research inputs, not implementation or test oracles. Preserve the routing: reference observation → independent validation/project decision → established public seam → test/implementation.
- Do not copy or mechanically transform external code, comments, documentation prose, tests, distinctive naming, module structure, control flow, or product expression.
- A reference-derived observation must not directly become an expected test value or architecture choice. If the expected behavior cannot be justified without the reference, research or decide first.

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