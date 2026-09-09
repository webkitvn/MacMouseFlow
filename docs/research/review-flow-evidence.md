# AI-driven review/merge flow evidence

## Question

Những facts/evidence (sự kiện/bằng chứng) nào từ lịch sử pull request của repository và primary sources (nguồn sơ cấp) đủ mạnh để làm input (đầu vào) cho quyết định về review/merge lifecycle (vòng đời review/hợp nhất), đặc biệt về design review timing (thời điểm review thiết kế), small batches (lô thay đổi nhỏ), AI-assisted delivery (phân phối có AI hỗ trợ), review closure (đóng vòng review), và cost of late discovery (chi phí phát hiện muộn)?

Research này chỉ ghi facts, failure patterns (mẫu thất bại), counter-evidence (bằng chứng phản bác), và decision implications (hệ quả cần đưa vào quyết định). Nó **không** tự biến external best practice (thực hành tốt bên ngoài) thành repository policy (chính sách repository), và không chốt workflow (quy trình) thay cho các Wayfinder decision ticket (ticket quyết định Wayfinder) kế tiếp.

Snapshot (ảnh chụp trạng thái): 2026-09-09, sau khi PR #81 đã merge.

## Method

Local evidence (bằng chứng cục bộ) được đọc từ PR #69, #70, #81, Issue #82 và các review/comment liên quan. External evidence (bằng chứng bên ngoài) chỉ dùng primary sources (nguồn sơ cấp) của Google Engineering Practices và DORA/Google.

Raw counts (số đếm thô) như commit, file và lines changed chỉ được dùng làm context (bối cảnh), không được xem là nguyên nhân hay threshold (ngưỡng) chính sách. Trọng tâm là semantic surface (bề mặt ngữ nghĩa), mechanism change (thay đổi cơ chế), loại blocker (vấn đề chặn), và thời điểm phát hiện.

## Local evidence matrix

| Evidence | Observed facts | Failure / success pattern | Counter-evidence | Decision implication, not policy |
| --- | --- | --- | --- | --- |
| PR #69 — `M0-S1: establish repository verification substrate` | Merged; 42 commits, 26 files, +906/-14. Một review bot tìm ra contract bug (lỗi hợp đồng) xác định được: test đòi `scripts/check_toolchain.py` trong khi change tạo `scripts/verify_toolchain.py`, khiến canonical test path (đường kiểm thử chuẩn) hỏng. PR body cuối cùng ghi rõ merge-ready và cảnh báo không mở rộng slice (lát cắt) bằng thêm tooling/process controls (công cụ/kiểm soát quy trình). | Một change lớn theo số dòng không tự động tạo review loop (vòng review) ngữ nghĩa dài. Blocker chính quan sát được là deterministic repository-contract mismatch (sai lệch hợp đồng repository xác định được), cộng các acceptance gates (cổng nghiệm thu) quản trị repository. | Đây vẫn là change rộng và 42 commits; không thể suy ra rằng large PR (PR lớn) là an toàn. Nó chỉ phản bác việc dùng kích thước thô làm predictor (biến dự đoán) duy nhất. | Không dùng hard line/commit threshold (ngưỡng cứng số dòng/commit) làm risk trigger (tín hiệu kích hoạt rủi ro) duy nhất. Cần phân loại theo semantic risk (rủi ro ngữ nghĩa) và acceptance surface (bề mặt nghiệm thu). |
| PR #70 — `feat: add guardrail registry` | Merged; 7 commits, 6 files, +1034/-3. Review ban đầu tìm các vấn đề về fixed cardinality (số lượng cố định), custom-registry mutation (sửa registry tùy chỉnh), lifecycle evolution (tiến hóa vòng đời), YAML semantics (ngữ nghĩa YAML), README drift (trôi tài liệu). Các re-review (review lại) tiếp tục phát hiện folded/quoted scalar semantics (ngữ nghĩa scalar gập/trích dẫn), YAML core typing (kiểu lõi YAML), textual typing (kiểu văn bản), cold-start scope/trigger (phạm vi/tín hiệu khởi động lạnh), plain scalar grammar (ngữ pháp scalar thuần), bare indicators/trailing colon (ký hiệu trần/dấu hai chấm cuối). Review cuối xác nhận không còn merge blocker và **không tiếp tục** mở rộng sang các YAML feature (tính năng YAML) ngoài conservative subset contract (hợp đồng tập con bảo thủ) đã thống nhất. | Nhiều vòng review có thể là hợp lệ khi root contract (hợp đồng gốc) còn sai: ở đây validator (bộ xác thực) tuyên bố chứng nhận một subset YAML nên các semantic mismatch (sai lệch ngữ nghĩa) trong subset đó là correctness defects (lỗi tính đúng), không chỉ nit (góp ý nhỏ). Review closure chỉ xuất hiện khi supported subset (tập con được hỗ trợ) được nói rõ và final review (review cuối) dùng boundary (ranh giới) đó để từ chối mở rộng scope. | Nếu đóng review quá sớm chỉ vì “đã nhiều vòng”, PR này có thể merge một validator chứng nhận sai semantics. Vì vậy review-round count (số vòng review) tự nó không thể là stop rule (quy tắc dừng). | Final merge contract (hợp đồng hợp nhất cuối) cần explicit scope boundary (ranh giới phạm vi rõ) và blocker admission (điều kiện tiếp nhận blocker), nhưng vẫn phải cho phép blocker mới nếu nó vi phạm chính root contract đã freeze (đóng băng). |
| PR #81 — `feat: add Rust input engine C ABI (#53)` | Merged; 10 commits, 26 files, +2117/-10. Initial review (review đầu) tìm panic-hook hot-path conflict (xung đột móc panic trên đường xử lý nóng), test-seam concern (lo ngại seam kiểm thử), và owner leak (rò rỉ chủ sở hữu). Test-seam finding sau đó bị retracted (rút lại) khi đối chiếu canonical Issue #8; owner leak được sửa. Panic-hook question (câu hỏi móc panic) được tách thành Issue #82. Resolution #82 chọn process-lifetime Rust-FFI-owned hook policy (chính sách móc panic toàn vòng đời tiến trình do Rust FFI sở hữu). Sau implementation (triển khai), review tiếp tục tìm: waiting-based `Condvar` deadlock (bế tắc do chờ bằng biến điều kiện), public `Busy`/`Panic` status ambiguity (mơ hồ trạng thái công khai), và first-install from already-panicking thread abort path (đường abort khi cài lần đầu từ luồng đang panic). Mỗi finding này đều có concrete correctness/contract basis (cơ sở tính đúng/hợp đồng cụ thể). Review `5140102965` đã freeze scope (đóng băng phạm vi) và giới hạn blocker mới vào canonical acceptance/guardrail violation (vi phạm nghiệm thu/rào chắn chuẩn), reproducible correctness/safety defect (lỗi tính đúng/an toàn tái hiện được), hoặc missing mandatory evidence (thiếu bằng chứng bắt buộc). Final review `5149317628` PASS và nói không khởi động lại vòng `finding -> patch -> finding` nếu head (đầu nhánh) không đổi hoặc không có concrete evidence (bằng chứng cụ thể) thuộc blocker class đã cho phép. | Đây là strongest local evidence (bằng chứng cục bộ mạnh nhất) cho late mechanism discovery (phát hiện cơ chế muộn): một quyết định global-state/concurrency (trạng thái toàn cục/đồng thời) được đưa vào giữa PR, rồi các fix (bản sửa) hợp lệ liên tiếp phơi ra deadlock, contract ambiguity và runtime abort path. Chi phí không phải do review “khó tính”, mà do mechanism-level semantic surface (bề mặt ngữ nghĩa cấp cơ chế) chưa được stress-test sớm. | Cũng là counter-evidence chống stop rule quá cứng: sau khi blocker-admission rule được freeze, vẫn xuất hiện thêm **hai** blocker hợp lệ vì chúng là public-contract/runtime defects (lỗi hợp đồng công khai/runtime) thật. Closure rule không thể bảo đảm “không có blocker mới”; nó chỉ loại preference/refactor/speculation (sở thích/tái cấu trúc/suy đoán) khỏi merge blockers. | Risky mechanism (cơ chế rủi ro) như process-global state (trạng thái toàn tiến trình), lock/wait (khóa/chờ), concurrency/reentrancy (đồng thời/tái nhập), ABI semantics (ngữ nghĩa ABI), lifecycle ownership (quyền sở hữu vòng đời) cần được xem xét semantic design (thiết kế ngữ nghĩa) sớm hơn code-complete review (review khi code đã hoàn thiện). Khi review fix tạo hoặc thay đổi mechanism, cần một explicit escalation point (điểm leo thang rõ), không mặc định tiếp tục patch trong cùng PR. |
| Issue #82 — process-wide panic-hook ownership | Initial Resolution (quyết định ban đầu) phải được supersede/clarify (thay thế/làm rõ) nhiều lần: fail-fast during installation (lỗi nhanh khi đang cài), `Busy` vs `Panic`, và reject first install from already-panicking thread (từ chối cài lần đầu từ luồng đang panic). Completion evidence chỉ được ghi sau final PR PASS. | Decision artifact (tạo phẩm quyết định) có thể đúng ở high level (mức cao) nhưng vẫn thiếu observable edge semantics (ngữ nghĩa biên quan sát được). Khi implementation reveals new evidence (triển khai phơi ra bằng chứng mới), canonical decision phải được corrected (sửa chuẩn), không để code âm thầm khác decision. | Không có bằng chứng rằng mọi architecture decision (quyết định kiến trúc) cần prototype (nguyên mẫu) trước; ở đây vấn đề cụ thể là global panic-hook + concurrency/reentrancy. | Preflight/decision contract (hợp đồng preflight/quyết định) nên ghi explicit assumptions (giả định rõ) và edge behavior (hành vi biên) cho mechanism rủi ro, nhưng #84 không quyết định exact format (định dạng chính xác). |

### Local source pointers

- PR #69: https://github.com/webkitvn/MacMouseFlow/pull/69
- PR #69 deterministic contract finding: https://github.com/webkitvn/MacMouseFlow/pull/69#issuecomment-5467986200
- PR #70: https://github.com/webkitvn/MacMouseFlow/pull/70
- PR #70 initial guardrail-registry review summary: https://github.com/webkitvn/MacMouseFlow/pull/70#issuecomment-5539729085
- PR #70 final closure review: https://github.com/webkitvn/MacMouseFlow/pull/70#pullrequestreview-5114183551
- PR #81: https://github.com/webkitvn/MacMouseFlow/pull/81
- PR #81 initial contract review: https://github.com/webkitvn/MacMouseFlow/pull/81#pullrequestreview-5131050582
- PR #81 re-review retracting the test-seam finding and isolating #82: https://github.com/webkitvn/MacMouseFlow/pull/81#pullrequestreview-5131980106
- PR #81 mechanism-level deadlock handoff and blocker-admission rule: https://github.com/webkitvn/MacMouseFlow/pull/81#pullrequestreview-5140102965
- PR #81 public-status contract blocker: https://github.com/webkitvn/MacMouseFlow/pull/81#pullrequestreview-5148666577
- PR #81 already-panicking-thread runtime blocker: https://github.com/webkitvn/MacMouseFlow/pull/81#pullrequestreview-5149003933
- PR #81 final PASS: https://github.com/webkitvn/MacMouseFlow/pull/81#pullrequestreview-5149317628
- Issue #82: https://github.com/webkitvn/MacMouseFlow/issues/82
- Issue #82 initial Resolution: https://github.com/webkitvn/MacMouseFlow/issues/82#issuecomment-5579092930
- Issue #82 fail-fast correction: https://github.com/webkitvn/MacMouseFlow/issues/82#issuecomment-5583611718
- Issue #82 `Busy` clarification: https://github.com/webkitvn/MacMouseFlow/issues/82#issuecomment-5594274446
- Issue #82 already-panicking-thread clarification: https://github.com/webkitvn/MacMouseFlow/issues/82#issuecomment-5594736007
- Issue #82 completion evidence: https://github.com/webkitvn/MacMouseFlow/issues/82#issuecomment-5595228307

## External primary-source evidence

| Source | Primary-source claim | What it supports | What it does **not** prove for this repository |
| --- | --- | --- | --- |
| Google Engineering Practices — Navigating a CL in review | Reviewer nên nhìn broad view (toàn cảnh) và main/important parts (phần chính/quan trọng) trước; nếu có major design problem (vấn đề thiết kế lớn), gửi comment ngay vì review phần còn lại có thể lãng phí và developer có thể đang xây tiếp trên design sai. Nếu CL quá lớn để xác định phần chính, có thể yêu cầu split (tách). | Early design review (review thiết kế sớm) giảm rework (làm lại) khi direction/design (hướng/thiết kế) sai. | Không chứng minh mọi change cần một preflight phase (giai đoạn preflight) riêng; đây là review guidance (hướng dẫn review), không phải repository workflow mandate (mệnh lệnh workflow repository). |
| Google Engineering Practices — The Standard of Code Review | Primary goal (mục tiêu chính) là code health (sức khỏe codebase). Reviewer nên approve khi change chắc chắn cải thiện code health dù chưa hoàn hảo; không seek perfection (tìm sự hoàn hảo); technical facts/data (sự kiện/dữ liệu kỹ thuật) thắng preference (sở thích); unresolved conflict (xung đột chưa giải quyết) nên escalate (leo thang), không để CL treo vô hạn. | Review closure cần phân biệt blocker thật với nit/preference; forward progress (tiến độ) là một phần của quality standard (tiêu chuẩn chất lượng). | Không cung cấp exact blocker taxonomy (phân loại blocker chính xác) cho repository này. |
| Google Engineering Practices — What to look for | Overall design là phần quan trọng nhất; reviewer phải nghĩ về concurrency (đồng thời), deadlock/race (bế tắc/tranh chấp); cần cảnh giác over-engineering (thiết kế quá mức) và chỉ giải bài toán hiện tại đã biết, không speculative future (tương lai suy đoán). | Global state/concurrency mechanism (cơ chế trạng thái toàn cục/đồng thời) xứng đáng scrutiny (soi xét) cao; future generalization (khái quát hóa tương lai) không nên tự động thành blocker. | Không nói rằng concurrency changes luôn phải split PR hoặc luôn cần design ticket. |
| Google Engineering Practices — Small CLs | Small/self-contained CLs (CL nhỏ/tự chứa) review nhanh và kỹ hơn, ít bug và ít wasted work (công việc lãng phí) khi direction sai, dễ rollback (hoàn tác). “Small” là conceptual/self-contained (khái niệm/tự chứa), không phải hard line count (số dòng cứng). Google cũng mô tả stacked changes (các change xếp chồng) và tách refactor khỏi feature/bugfix khi refactor đủ lớn. | Conceptual batch size (kích thước lô theo khái niệm) và mechanism separation (tách cơ chế) là inputs hợp lý cho #87. | Không chứng minh một quy tắc “one PR = one risky mechanism” là luôn đúng; Google nói reviewer judgment (phán đoán reviewer) và self-contained change. |
| DORA — Working in small batches | Small batches (lô nhỏ) rút ngắn feedback loop (vòng phản hồi), hỗ trợ course-correct (điều chỉnh hướng), dự đoán software delivery/organizational performance (hiệu suất phân phối phần mềm/tổ chức). DORA nói trong generative AI era (kỷ nguyên AI tạo sinh), small batches càng quan trọng; AI có thể tăng delivery instability (bất ổn phân phối), và massive AI-generated PRs (PR lớn do AI tạo) tăng cognitive review load (tải nhận thức khi review). DORA khuyến nghị work unit (đơn vị công việc) thường ở mức hours to a couple days (vài giờ đến vài ngày); batch > một tuần là quá lớn theo guidance này. | AI-assisted workflow (workflow có AI hỗ trợ) nên ưu tiên decomposition (phân rã) và fast feedback (phản hồi nhanh) hơn raw code generation speed (tốc độ sinh code thô). | Không nên copy các mốc thời gian này thành repository hard gate (cổng cứng) nếu chưa có local decision; DORA nghiên cứu ở population (quần thể) rộng, không phải causal proof (chứng minh nhân quả) riêng cho repository. |
| DORA 2025 State of AI-assisted Software Development | DORA 2025 mô tả AI là amplifier (bộ khuếch đại): nó khuếch đại cả strengths (điểm mạnh) và dysfunctions (rối loạn) hiện có của tổ chức. | Process weakness (điểm yếu quy trình) có thể bị AI tăng tốc thay vì được AI chữa; phù hợp với việc xem review-loop pathology (bệnh lý vòng review) là system issue (vấn đề hệ thống), không chỉ “AI viết code dở”. | Không tự xác định mechanism nào của repository phải có preflight, merge contract hay stacked PR. |

### External primary sources

- Google Engineering Practices — Navigating a CL in review: https://google.github.io/eng-practices/review/reviewer/navigate.html
- Google Engineering Practices — The Standard of Code Review: https://google.github.io/eng-practices/review/reviewer/standard.html
- Google Engineering Practices — What to look for in a code review: https://google.github.io/eng-practices/review/reviewer/looking-for.html
- Google Engineering Practices — Small CLs: https://google.github.io/eng-practices/review/developer/small-cls.html
- DORA — Working in small batches: https://dora.dev/capabilities/working-in-small-batches/
- DORA 2025 report landing page: https://dora.dev/dora-report-2025/
- Google Research — DORA 2025 State of AI-assisted Software Development Report: https://research.google/pubs/dora-2025-state-of-ai-assisted-software-development-report/

## Party Meeting — competing interpretations

Các position (lập trường) dưới đây cố ý giữ xung đột; research không giả vờ chúng đã đồng thuận.

### Position A — Mandatory semantic preflight for every execution issue

Argument (lập luận): Google nói major design comments nên xuất hiện sớm, DORA nói AI làm large-batch risk (rủi ro lô lớn) tệ hơn, và PR #81 cho thấy late design discovery (phát hiện thiết kế muộn) rất đắt. Vì vậy mọi execution issue (issue thực thi) nên qua preflight semantic review (review ngữ nghĩa trước thực thi).

Objection (phản biện): local evidence không chứng minh universal preflight (preflight cho mọi change). PR #69 không cho thấy một semantic loop tương tự; PR #70 cho thấy review sâu vẫn có thể cần nhiều vòng ngay cả khi change tương đối hẹp về file count (số file). Mandatory preflight có thể duplicate (lặp lại) code review, tăng ceremony (thủ tục), và chính nó trở thành bottleneck (nút thắt) cho low-risk change (thay đổi rủi ro thấp).

Status: **not established**.

### Position B — Keep planning light; code review is the only semantic gate

Argument: code là concrete artifact (tạo phẩm cụ thể) tốt nhất để reviewer reason about (suy luận). Preflight có thể dự đoán sai và tạo speculative abstractions (trừu tượng suy đoán). Google cũng yêu cầu forward progress và không seek perfection.

Objection: PR #81 là direct counterexample (phản ví dụ trực tiếp) cho high-risk mechanism (cơ chế rủi ro cao). Process-global panic hook, waiting, reentrancy và ABI status semantics chỉ được làm rõ sau nhiều implementation cycles (chu kỳ triển khai). Một số lỗi này thuộc design property (thuộc tính thiết kế), không phải typo/local bug (lỗi cục bộ), nên đợi code-complete review làm tăng rework (làm lại).

Status: **not sufficient for high-risk work**.

### Position C — Risk-triggered semantic preflight + frozen merge contract + mechanism escalation

Argument: dùng preflight chỉ khi semantic surface có các trigger (tín hiệu) như global state, lock/wait, concurrency/reentrancy, lifecycle owner, public ABI/API, persistence/schema, new dependency hoặc architecture responsibility (trách nhiệm kiến trúc); dùng final frozen contract (hợp đồng cuối đóng băng) để ngăn preference/speculation thành blocker; nếu review fix tạo một risky mechanism mới, escalate (leo thang) thay vì cứ patch.

Objection: exact trigger list (danh sách trigger chính xác), PASS authority (thẩm quyền PASS), freeze semantics (ngữ nghĩa đóng băng), và stacked-PR rule (quy tắc PR xếp chồng) chưa có local evidence đủ để chốt ngay. Nếu trigger list quá rộng, Position C suy biến thành Position A; nếu quá hẹp, nó không chặn được PR #81-style late discovery.

Status: **best-supported hypothesis (giả thuyết được bằng chứng hỗ trợ tốt nhất), nhưng vẫn cần decision tickets #85–#88 để thành policy**.

## Findings that are strong enough to carry forward

1. **Raw PR size is a weak standalone risk signal (tín hiệu rủi ro độc lập yếu).** PR #69 lớn theo commit/file nhưng không biểu hiện cùng failure pattern với #81; PR #70 ít commit/file hơn nhưng root parser contract vẫn tạo nhiều semantic review rounds. Nếu dùng size, chỉ nên dùng như context phụ.

2. **Semantic/mechanism risk is a stronger discriminator (bộ phân biệt mạnh hơn).** Local stress case #81 tập trung vào process-global state, concurrency/reentrancy, lock/wait, panic lifecycle và public ABI semantics. Đây là loại surface mà Google cũng yêu cầu design/concurrency scrutiny cao.

3. **Review-loop count is not itself a failure metric (chỉ số thất bại).** PR #70 và #81 đều có nhiều vòng nhưng nhiều vòng đã bắt lỗi thật. Metric hữu ích hơn là: new blocker after claimed readiness (blocker mới sau khi tuyên bố sẵn sàng), review-induced mechanism change (thay đổi cơ chế do review), retracted blocker (blocker bị rút lại), blocker family (họ blocker), và elapsed review/merge time (thời gian review/hợp nhất).

4. **A closure boundary is necessary but not sufficient.** PR #70 cho thấy explicit subset boundary có thể dừng scope creep (trượt phạm vi). PR #81 cho thấy blocker-admission rule có thể loại refactor/generalization/cosmetic work (tái cấu trúc/khái quát hóa/chỉnh hình thức), nhưng vẫn phải cho phép concrete contract/runtime defect (lỗi hợp đồng/runtime cụ thể) xuất hiện sau đó.

5. **Review-induced mechanism changes deserve an explicit escalation point.** Khi fix chuyển từ local correction (sửa cục bộ) sang state machine/global owner/lock-wait/public-contract change (thay đổi máy trạng thái/chủ sở hữu toàn cục/khóa-chờ/hợp đồng công khai), tiếp tục patch trong cùng PR làm tăng semantic surface và có thể tạo blocker mới. Research ủng hộ việc #87 phải quyết định rõ khi nào split/stack (tách/xếp chồng), nhưng chưa chọn rule.

6. **Small batch should mean conceptually self-contained (tự chứa theo khái niệm), not a hard LOC/commit limit (không phải giới hạn cứng số dòng/commit).** Đây là điểm local evidence và Google guidance hội tụ. DORA bổ sung rằng discipline (kỷ luật) này đặc biệt quan trọng khi AI tăng tốc lượng code tạo ra.

7. **Canonical decisions must remain correctable by new evidence.** Issue #82 phải được supersede/clarify nhiều lần khi implementation/review lộ ra deadlock, status ambiguity và runtime abort path. Freeze (đóng băng) không thể có nghĩa “cấm sửa decision”; nó phải có explicit reopen/supersede authority (thẩm quyền mở lại/thay thế) nếu xuất hiện concrete evidence.

## Counter-evidence and limits

- Không có bằng chứng rằng “nhiều review rounds = process failure”. Một số round của #70/#81 là precisely what prevented incorrect merge (chính thứ đã ngăn merge sai).
- Không có bằng chứng rằng preflight có thể phát hiện mọi runtime interaction (tương tác runtime). Final code review và executable evidence (bằng chứng thực thi) vẫn cần.
- Không có bằng chứng local đủ để đặt hard thresholds như “>N lines”, “>N commits”, “>N days” hoặc “one risky mechanism per PR” thành mandatory rule (quy tắc bắt buộc).
- External sources hỗ trợ direction (hướng) chứ không quyết định repository-specific enforcement surface (bề mặt cưỡng chế riêng của repository).
- PR #81 đã merge thành công; vì vậy evidence không nói mechanism-heavy work (công việc nặng cơ chế) là không thể làm trong một PR. Nó nói late mechanism discovery có serial rework cost (chi phí làm lại nối tiếp) và cần được decision tickets kế tiếp xử lý.

## Inputs for the next Wayfinder decisions

Research đủ mạnh để #85–#88 không phải đọc lại toàn bộ lịch sử PR, nhưng các câu sau vẫn phải được quyết định, không được coi là facts:

- #85: exact risk triggers (tín hiệu rủi ro chính xác), low-risk fast path (đường nhanh rủi ro thấp), preflight output (đầu ra preflight), STOP/PASS authority (thẩm quyền STOP/PASS), và freeze semantics.
- #86: canonical Frozen Merge Contract (Hợp đồng Hợp nhất Đóng băng), blocker-admission classes (lớp blocker được phép), required finding payload (payload phát hiện bắt buộc), và reopen/supersede authority.
- #87: local correction vs mechanism change (sửa cục bộ so với đổi cơ chế), stacked PR policy (chính sách PR xếp chồng), và khi nào review-induced mechanism phải tách khỏi PR hiện tại.
- #88: final lifecycle (vòng đời cuối), artifact ownership (quyền sở hữu tạo phẩm), archive ordering (thứ tự lưu trữ), và metrics (chỉ số) dùng để phát hiện workflow pathology (bệnh lý workflow) mà không tạo Goodhart pressure (áp lực tối ưu sai mục tiêu).

## Research conclusion

Evidence hội tụ vào một kết luận hẹp: vấn đề cần giải không phải là “review ít hơn” hay “review nhiều hơn”, mà là **đưa design scrutiny (soi xét thiết kế) về sớm cho semantic surfaces rủi ro, giữ batches tự chứa theo khái niệm, và có closure/escalation contract rõ khi review bắt đầu tạo hoặc thay đổi mechanism**.

Tuy nhiên exact workflow (workflow chính xác) vẫn chưa được quyết định. #84 chỉ làm nhiệm vụ biến kinh nghiệm từ #69/#70/#81 và primary research thành evidence base (nền bằng chứng) cho các decision ticket kế tiếp.
