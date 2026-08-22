# Minimum macOS deployment target research

## Question

M0 + v0.1 nên đặt minimum macOS deployment target (mục tiêu macOS tối thiểu) ở phiên bản nào để cân bằng API simplicity (độ đơn giản API), CI testability (khả năng kiểm thử trên CI), reliability (độ tin cậy), user reach (độ phủ người dùng) và ready-for-AI maintainability (khả năng AI bảo trì)?

## Findings

### Service Management

Apple ghi rõ `SMAppService` dùng trên macOS 13 trở lên để đăng ký và điều khiển LoginItem, LaunchAgent và LaunchDaemon. Vì vậy nếu target thấp hơn macOS 13, project phải duy trì legacy path (đường cũ) cho Service Management.

Source: https://developer.apple.com/documentation/servicemanagement/smappservice

### HID input

`IOHIDManager` cung cấp device discovery/removal (phát hiện/gỡ thiết bị) và nhận input events (sự kiện đầu vào) ở tầng HID. API này đủ làm compatibility baseline (đường cơ sở tương thích) cho việc thử nghiệm device-aware input (đầu vào nhận biết thiết bị) mà không buộc deployment target phải nâng chỉ để dùng API HID mới hơn.

Source: https://developer.apple.com/documentation/iokit/iohidmanager_h

Apple Core HID cung cấp API hiện đại hơn cho discovery/interaction (phát hiện/tương tác) và expose (cung cấp) thuộc tính như `isBuiltIn`, `vendorID`, `productID`, `transport`, `uniqueID`. Đây là lựa chọn có thể đánh giá trong runtime-boundary decision (quyết định ranh giới thời gian chạy), nhưng không nên tự nó ép minimum target của M0 + v0.1 nếu `IOHIDManager` đã đáp ứng correctness (tính đúng) cần thiết.

Sources:
- https://developer.apple.com/documentation/corehid
- https://developer.apple.com/documentation/corehid/hiddevicemanager/devicematchingcriteria

### Current CI reality

GitHub đã retire (ngừng) hosted `macos-13` runner vào ngày 4/12/2025 và khuyến nghị chuyển sang `macos-14` hoặc `macos-15`.

Source: https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/

Tại thời điểm nghiên cứu, standard GitHub-hosted macOS runners (runner macOS do GitHub cung cấp) gồm `macos-14`, `macos-15`, `macos-26` cùng các biến thể Intel tương ứng; không còn `macos-13`.

Source: https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job

### Current Apple maintenance signal

Apple vẫn phát hành security/stability updates (cập nhật bảo mật/ổn định) cho macOS Sonoma 14 trong năm 2026; trang update của Apple ghi macOS Sonoma 14.8.9 và được cập nhật ngày 6/8/2026.

Source: https://support.apple.com/en-us/109035

## Options considered

### macOS 13

Ưu điểm: là mốc thấp nhất có `SMAppService`, tăng user reach (độ phủ người dùng).

Nhược điểm: GitHub-hosted runner đã retire, nên tuyên bố support (hỗ trợ) macOS 13 đòi self-hosted/manual verification (xác minh tự host/thủ công) hoặc chấp nhận một platform claim (cam kết nền tảng) không được CI kiểm chứng. Điều này đi ngược ready-for-AI maintainability (khả năng AI bảo trì).

### macOS 14

Ưu điểm: giữ `SMAppService`, còn được Apple cập nhật trong 2026, là hosted runner thấp nhất hiện có trên GitHub Actions, và không buộc thêm legacy Service Management path (đường Service Management cũ). Cho phép matrix (ma trận) 14/15/26 mà agent có thể chạy lặp lại.

Nhược điểm: bỏ macOS 13 dù API chính vẫn có thể chạy ở đó.

### macOS 15

Ưu điểm: gần các API hiện đại hơn và giảm thêm compatibility surface (bề mặt tương thích).

Nhược điểm: cắt macOS 14 trong khi macOS 14 vẫn có hosted CI và còn được Apple bảo trì; chưa có capability (khả năng) M0 + v0.1 nào đã chứng minh cần macOS 15.

## Recommendation

Chọn macOS 14 làm minimum deployment target (mục tiêu macOS tối thiểu) cho M0 + v0.1.

Quy tắc đi kèm:

- CI compatibility gate (cổng tương thích CI) phải có ít nhất một job trên `macos-14`.
- Không tạo compatibility shim (lớp tương thích) hoặc legacy helper path chỉ để giữ macOS 13.
- API chỉ có ở macOS 15+ không được trở thành correctness dependency (phụ thuộc tính đúng) của v0.1 nếu có đường macOS 14 hợp lý.
- Nếu runtime architecture (kiến trúc thời gian chạy) sau này chứng minh một API 15+ giúp giảm đáng kể complexity/risk (độ phức tạp/rủi ro), có thể mở decision ticket mới để nâng target; không duy trì hai runtime paths chỉ để giữ 14.
- Minimum target phải được review lại khi chuẩn bị v1 public release (bản phát hành công khai v1), dựa trên user demand (nhu cầu người dùng), Apple support state (trạng thái hỗ trợ của Apple), CI availability (khả dụng CI) và architecture (kiến trúc) thực tế.
