# AI Agent Rules

Read this file before changing code, tests, build files, documentation, or planning artifacts.

## Source of truth

- `AGENTS.md`: stable repository-wide agent rules.
- GitHub Issues: live project context, decisions, status, milestones, hierarchy, dependencies, release gates, and artifact pointers.
- `CONTEXT.md`: canonical domain language.
- `docs/adr/`: hard-to-reverse architecture decisions.
- `docs/research/`: research evidence.
- Code, tests, and build files: implementation truth.

Do not treat chat history as project truth. If canonical sources conflict, report the drift in the active Issue and resolve it before continuing.

## Cold start

Use `gh` as the default project interface.

```bash
gh issue list -R OWNER/REPO --label wayfinder:map --state open --json number,title,url

gh issue view ISSUE -R OWNER/REPO --comments \
  --json number,title,body,state,stateReason,labels,milestone,parent,subIssues,blockedBy,blocking,comments,url

gh repo read-file CONTEXT.md -R OWNER/REPO \
  || gh api repos/OWNER/REPO/contents/CONTEXT.md -H 'Accept: application/vnd.github.raw+json'
```

Follow Issue pointers to ADRs and research only when needed.

## Working rules

- Work from an explicit GitHub Issue for planned work.
- Check dependencies before starting; claim an unassigned frontier Issue before working it.
- Keep changes small and vertical around an observable outcome, not a technical layer.
- Use domain terms from `CONTEXT.md`; do not invent competing vocabulary.
- Do not introduce new process boundaries, helpers, IPC, HID takeover, or other hard-to-reverse architecture changes without a decision Issue and ADR.
- Update the active Issue when a material fact or decision changes what later agents need to know.
- External products and codebases may inform behavioral research, but do not copy code, comments, documentation prose, distinctive naming, or distinctive structure.

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
```

Git hooks and GitHub Actions must call these commands instead of duplicating verification logic. Hooks are feedback gates, not final acceptance gates.

Test behavior through public seams. Mock or fake only at system boundaries. Strict latency evidence comes from the reference Mac, not hosted CI timing.

Hot-path diagnostics must use bounded enqueue/buffering only. Prefer dropping trace data over blocking input.

## Wayfinder planning

- The open Issue labeled `wayfinder:map` is the planning index.
- Decision details live in resolution comments, not duplicated in the map.
- Milestones represent releases; labels represent work type; parent/sub-issue represents decomposition; blocked-by/blocking represents dependency.
- Prefer native GitHub relationships over Markdown dependency lists.
- Resolve at most one non-research Wayfinder ticket per planning session.

Keep this file short and stable. Do not copy transient milestones, frontier state, dependency graphs, or full decision bodies into it.