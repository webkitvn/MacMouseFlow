# AI Agent Rules (quy tắc cho tác nhân AI)

This file is the repository-wide operating contract (hợp đồng vận hành toàn kho) for AI coding agents (tác nhân lập trình AI). Read it before changing code, tests, build files, documentation, or GitHub planning artifacts.

## 1. Authority and source of truth (thẩm quyền và nguồn sự thật)

`AGENTS.md` defines stable agent behavior (hành vi ổn định của tác nhân). It does not duplicate volatile project state (trạng thái dự án dễ thay đổi).

Use these sources for their canonical responsibility (trách nhiệm chuẩn):

- GitHub Issues: current project context, decisions, status, milestone, hierarchy, dependencies, acceptance/release gates, and artifact pointers (ngữ cảnh, quyết định, trạng thái, cột mốc, phân cấp, phụ thuộc, cổng chấp nhận/phát hành và con trỏ tạo phẩm).
- `CONTEXT.md`: canonical domain language (ngôn ngữ miền chuẩn).
- `docs/adr/`: hard-to-reverse architecture decisions (quyết định kiến trúc khó đảo ngược).
- `docs/research/`: research evidence (bằng chứng nghiên cứu).
- Repository code/tests/build files: implementation truth (sự thật triển khai).

Do not rely on chat history as project truth. If a material decision exists only in chat, record it in the appropriate GitHub Issue before another agent is expected to depend on it.

If sources conflict, do not silently choose one. Surface the conflict in the active GitHub Issue and resolve the source-of-truth drift (lệch nguồn sự thật) before continuing.

## 2. Cold-start bootstrap (khởi động từ số 0)

An agent should be able to start with only `OWNER/REPO` and `gh` CLI (giao diện dòng lệnh gh).

Start by locating and reading the open Wayfinder map when planning is active:

```bash
gh issue list -R OWNER/REPO \
  --label wayfinder:map \
  --state open \
  --json number,title,url
```

Read the active issue, its comments, and the available native graph metadata (siêu dữ liệu đồ thị bản địa):

```bash
gh issue view ISSUE -R OWNER/REPO --comments \
  --json number,title,body,state,stateReason,labels,milestone,parent,subIssues,blockedBy,blocking,comments,url
```

Read canonical repository context without requiring a browser UI:

```bash
gh repo read-file AGENTS.md -R OWNER/REPO \
  || gh api repos/OWNER/REPO/contents/AGENTS.md -H 'Accept: application/vnd.github.raw+json'

gh repo read-file CONTEXT.md -R OWNER/REPO \
  || gh api repos/OWNER/REPO/contents/CONTEXT.md -H 'Accept: application/vnd.github.raw+json'
```

Follow context pointers (con trỏ ngữ cảnh) from Issues to ADR/research files as needed. Do not preload unrelated documents.

## 3. Working discipline (kỷ luật làm việc)

- Work from an explicit GitHub Issue whenever the change is part of planned work.
- Before work, inspect dependency/blocking state (trạng thái phụ thuộc/chặn) and do not start work that is still blocked.
- Keep changes small and vertical (nhỏ và theo lát dọc) around an observable capability/outcome (khả năng/kết quả quan sát được), not around technical layers.
- Do not introduce a new architecture boundary, helper process, IPC (giao tiếp liên tiến trình), HID takeover (chiếm HID), or other hard-to-reverse topology change without a decision Issue/ADR.
- Do not invent product/domain terminology. Read `CONTEXT.md` and use its canonical vocabulary.
- Update GitHub Issue context/status when a material implementation fact or decision changes what later agents need to know.

## 4. M0 + v0.1 architecture guardrails (hàng rào kiến trúc)

Until a later decision explicitly supersedes them:

- Runtime topology (cấu trúc thời gian chạy) is one SwiftUI/AppKit process with a native input adapter and a platform-neutral Rust engine.
- Swift/AppKit owns macOS lifecycle, permission state, `CGEventTap`, native event extraction/application, and platform I/O outside the input callback.
- Rust owns platform-neutral input normalization, domain semantics, configuration evaluation, and `Input Decision`.
- Swift ↔ Rust uses a narrow manual C ABI (giao diện C thủ công, hẹp) with fixed-layout value data (dữ liệu giá trị bố cục cố định) on the hot path (đường nóng).
- The input callback must not perform UI/MainActor work, disk I/O, network I/O, synchronous logging (ghi log đồng bộ), config parsing, or unbounded blocking/locking (chặn/khóa không giới hạn).
- On bridge/engine failure, fail open (mở an toàn): preserve the original input.
- Do not infer physical `Device Identity` (định danh thiết bị vật lý) from `Scroll Granularity` (độ hạt cuộn), timestamps, or undocumented correlation.
- v0.1 correctness (tính đúng) is limited to documented `LineBased` versus `PixelBased` scroll behavior; `PixelBased` is preserved by default unless a later decision changes scope.

Canonical architecture detail is in GitHub decision Issues and `docs/adr/`.

## 5. Verification contract (hợp đồng xác minh)

Canonical repository commands (lệnh chuẩn trong kho) are the single source of verification behavior. Hooks and GitHub Actions must call them rather than duplicating verification logic.

The ready-for-AI contract (hợp đồng sẵn sàng cho AI) requires this command surface:

```text
just check
just test
just ci
just benchmark
just smoke
just hooks-install
```

Expected semantics (ngữ nghĩa kỳ vọng):

- `just check`: fast deterministic formatting/lint/config validation (định dạng/kiểm tra tĩnh/xác thực cấu hình nhanh và xác định).
- `just test`: deterministic behavior/contract tests (kiểm thử hành vi/hợp đồng xác định).
- `just ci`: full remote-safe deterministic verification (xác minh xác định đầy đủ, an toàn chạy từ xa).
- `just benchmark`: strict reference-Mac latency gate (cổng độ trễ nghiêm ngặt trên máy Mac tham chiếu).
- `just smoke`: live macOS/TCC/Accessibility/`CGEventTap` smoke (kiểm tra khói hệ thống thật).
- `just hooks-install`: install repository-managed Git hooks (cài móc Git do kho quản lý), using `.githooks`/`core.hooksPath` unless superseded by the ready-for-AI decision.

Until a command is actually implemented, do not fake a passing result or silently substitute a different workflow. Follow the active implementation Issue and report the missing command as missing infrastructure (hạ tầng còn thiếu).

Git hooks are feedback gates (cổng phản hồi), not the final source of acceptance. `--no-verify` may bypass a hook, but it does not waive required tests or CI gates.

## 6. Test and performance rules (quy tắc kiểm thử và hiệu năng)

- Test behavior through public seams (điểm nối công khai), not private call graphs (đồ thị gọi riêng tư).
- Mock/fake (mô phỏng/giả lập) only at system boundaries (ranh giới hệ thống), not internal Rust modules or internal Swift collaborators merely to assert call order/count.
- Expected values must come from specifications/literal examples (đặc tả/ví dụ cụ thể), not from recomputing with the same production algorithm.
- Strict latency evidence (bằng chứng độ trễ nghiêm ngặt) comes from the reference Mac, not hosted CI timing.
- Do not add logging/allocation/locking on the input hot path without benchmark evidence (bằng chứng đo chuẩn) that the latency contract still passes.

Canonical latency/test details are defined by the test/latency decision Issue and its ADR.

## 7. Clean-room and provenance (phát triển độc lập và nguồn gốc)

The clean-room/provenance decision is tracked in its dedicated GitHub Issue. Until that decision is resolved, apply the conservative rule:

- External products/codebases may inform behavioral questions (câu hỏi hành vi) and research.
- Do not copy external code, comments, documentation prose, distinctive naming, or distinctive code/file structure into this repository.
- Record external research evidence in the relevant research/decision Issue or research artifact so later agents can distinguish evidence from implementation choices.

When the clean-room decision is resolved, update this section to point to its canonical policy without duplicating volatile detail.

## 8. Observability and diagnostics (khả năng quan sát và chẩn đoán)

The detailed observability/debug logging contract is still owned by its dedicated GitHub Issue until resolved.

Standing rules already fixed by architecture/testing decisions:

- Hot-path logging must be bounded enqueue/buffer only (xếp hàng/đệm có giới hạn), never synchronous disk/network output.
- Dropping diagnostic trace under overload is preferable to blocking input.
- Tap timeout/disable/re-enable, bridge failure, Rust error/panic containment, and fail-open behavior must be diagnosable (chẩn đoán được).
- Do not claim traceability beyond what the implemented schema/sinks actually provide.

## 9. GitHub planning rules (quy tắc lập kế hoạch GitHub)

When operating in Wayfinder planning mode (chế độ lập kế hoạch Wayfinder):

- The issue labeled `wayfinder:map` is the canonical map/index (bản đồ/chỉ mục chuẩn).
- Decision detail lives in the decision Issue resolution, not duplicated in the map.
- Milestones (cột mốc) represent releases, labels represent work type, parent/sub-issue represents decomposition (phân rã), and blocked-by/blocking represents dependency (phụ thuộc).
- Native GitHub relationships/metadata are preferred over Markdown dependency duplication when available.
- Claim an unassigned frontier Issue before working it.
- Do not resolve more than one non-research Wayfinder ticket in one planning session.

## 10. Change this file carefully (thay đổi tệp này cẩn thận)

`AGENTS.md` is intentionally stable. Update it when repository-wide agent behavior changes, not for transient milestone status or one-off task instructions.

A change to this file should:

- be tied to a GitHub Issue/decision or an explicit owner instruction;
- avoid copying large decision bodies that belong in Issues/ADR/CONTEXT;
- preserve `gh`-only cold-start discoverability (khả năng khám phá khi khởi động chỉ bằng gh);
- keep rules testable or operational where possible.
