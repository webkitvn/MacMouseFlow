# macOS distribution research

## Question

Các yêu cầu hiện hành của Apple cho code signing (ký mã), notarization (công chứng), Hardened Runtime (môi trường chạy tăng cường), entitlements (quyền khai báo), App Sandbox (hộp cát ứng dụng), login items/helpers (mục khởi động/trợ lý), và direct distribution (phân phối trực tiếp) ảnh hưởng thế nào tới packaging/runtime architecture (kiến trúc đóng gói/thời gian chạy) của một macOS input utility (tiện ích đầu vào macOS)?

## Findings

### 1. Direct distribution (phân phối trực tiếp) dùng Developer ID

Apple phân biệt hai kênh chính cho phần mềm Mac: Mac App Store và direct distribution (phân phối trực tiếp). Với direct distribution, app dùng `Developer ID Application` certificate (chứng chỉ Developer ID Application); installer package (gói cài đặt) dùng `Developer ID Installer` khi cần. Developer ID certificates (chứng chỉ Developer ID) chỉ được cấp cho thành viên Apple Developer Program hoặc Apple Developer Enterprise Program.

Sources:
- https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac/
- https://developer.apple.com/help/account/certificates/certificates-overview
- https://developer.apple.com/help/glossary/developer-id-certificate/

### 2. Notarization (công chứng) là release gate (cổng phát hành) cho Developer ID software (phần mềm Developer ID)

Apple yêu cầu software (phần mềm) phân phối với Developer ID phải được notarize (công chứng) trên các macOS hiện đại. Notary service (dịch vụ công chứng) quét malicious content (nội dung độc hại), kiểm tra code-signing issues (lỗi ký mã), và tạo ticket có thể được staple (đính) vào artifact (tạo phẩm) để Gatekeeper xác minh ngay cả khi ticket online không sẵn có.

Từ ngày 1/11/2023, notary service không còn nhận upload bằng `altool` hoặc Xcode 13 trở xuống; automation (tự động hóa) mới phải dùng `notarytool`, Xcode mới, hoặc Notary API.

Sources:
- https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- https://developer.apple.com/documentation/security/customizing-the-notarization-workflow
- https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool
- https://developer.apple.com/documentation/notaryapi

### 3. Hardened Runtime (môi trường chạy tăng cường) và secure timestamp (dấu thời gian bảo mật) là yêu cầu notarization

Apple yêu cầu code-signing hợp lệ cho mọi executable (tệp thực thi), Developer ID signing identity (định danh ký Developer ID), Hardened Runtime, secure timestamp, và entitlements (quyền khai báo) đúng định dạng. `com.apple.security.get-task-allow=true` không được để trong distribution build (bản dựng phân phối). Nếu Hardened Runtime không bật, notarization báo lỗi.

Sources:
- https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- https://developer.apple.com/documentation/security/resolving-common-notarization-issues
- https://developer.apple.com/documentation/xcode/build-settings-reference

### 4. Sign nested code (mã lồng nhau) từ trong ra ngoài; không dùng `codesign --deep` để ký sản phẩm

Apple hướng dẫn xác định mọi code item (thành phần mã) cần ký và ký từ inside-out (trong ra ngoài). `--deep` không nên dùng để ký vì nó có thể áp cùng signing options/entitlements (tùy chọn ký/quyền khai báo) cho các thành phần cần cấu hình khác nhau và bỏ sót code ở vị trí không chuẩn. Nếu runtime sau này có helper/daemon (trợ lý/tiến trình nền), mỗi executable phải có signature/entitlements (chữ ký/quyền khai báo) phù hợp riêng.

Source:
- https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac/

### 5. `.zip` là container (vỏ đóng gói) hợp lệ và phù hợp với project Homebrew Cask tap (tap Homebrew Cask của dự án)

Apple liệt kê `.zip`, `.dmg` và installer package (gói cài đặt) là các container phổ biến cho direct distribution. Notarization workflow cũng hỗ trợ ZIP archive chứa app. ZIP không tự có code signature; integrity (tính toàn vẹn) dựa vào signature của code bên trong. Vì vậy một signed + notarized `.app` được đóng thành ZIP là artifact (tạo phẩm) hợp lý cho GitHub Release và Homebrew Cask trong M0/v0.1; chưa có lý do buộc phải thêm `.dmg` hoặc `.pkg` ở giai đoạn này.

Sources:
- https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution
- https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution

### 6. App Sandbox (hộp cát ứng dụng) không nên là constraint (ràng buộc) mặc định cho runtime can thiệp input (đầu vào)

Apple yêu cầu App Sandbox cho app phân phối qua Mac App Store. Với direct distribution + notarization, Hardened Runtime là bắt buộc còn App Sandbox là tùy chọn. Apple đồng thời liệt kê việc dùng accessibility APIs (API trợ năng) trong assistive apps (ứng dụng hỗ trợ) là hoạt động không tương thích với App Sandbox.

Consequence (hệ quả): với capability (khả năng) cần monitor/filter/control system input (giám sát/lọc/điều khiển đầu vào hệ thống), kiến trúc M0/v0.1 nên mặc định direct Developer ID distribution (phân phối Developer ID trực tiếp) và không bật App Sandbox trừ khi một prototype/research (nguyên mẫu/nghiên cứu) chứng minh capability cần thiết vẫn hoạt động đầy đủ. Mac App Store không phải distribution target (mục tiêu phân phối) cho đường tới v0.1.

Sources:
- https://developer.apple.com/documentation/xcode/preparing-your-app-for-distribution
- https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox

### 7. TCC permissions (quyền TCC) vẫn là runtime state (trạng thái thời gian chạy), không được giải quyết chỉ bằng code signing (ký mã)

Developer ID signing/notarization giúp Gatekeeper xác minh nguồn gốc và tính toàn vẹn của phần mềm; nó không thay thế user consent (sự đồng ý người dùng) cho privacy-protected capabilities (khả năng được bảo vệ riêng tư) như Input Monitoring/Accessibility (Giám sát đầu vào/Trợ năng). Permission state (trạng thái quyền) phải được UI/runtime quan sát và hướng dẫn riêng.

Sources:
- https://developer.apple.com/help/glossary/developer-id-certificate/
- https://support.apple.com/guide/mac-help/mchl4cedafb6/mac
- https://support.apple.com/guide/mac-help/mh43185/mac

### 8. `SMAppService` là API hiện hành cho login item/agent/daemon (mục khởi động/agent/daemon) trên macOS 13+

Apple cung cấp `SMAppService` từ macOS 13 để register/control (đăng ký/điều khiển) LoginItems, LaunchAgents và LaunchDaemons được nhúng trong main app bundle (gói ứng dụng chính). `mainApp` có thể dùng để launch main application at login (khởi động ứng dụng chính khi đăng nhập). LoginItem/LaunchAgent có thể register (đăng ký) ở user context (ngữ cảnh người dùng); LaunchDaemon cần admin approval (phê duyệt quản trị viên).

Bundle-based structure (cấu trúc dựa trên bundle) giảm nhu cầu installer script (script cài đặt) ghi trực tiếp vào `~/Library/LaunchAgents` hay `/Library/LaunchDaemons`.

Sources:
- https://developer.apple.com/documentation/servicemanagement/smappservice
- https://developer.apple.com/documentation/servicemanagement/updating-helper-executables-from-earlier-versions-of-macos
- https://developer.apple.com/documentation/servicemanagement/smappservice/mainapp
- https://developer.apple.com/documentation/servicemanagement/smappservice/register()

### 9. Privileged helper/LaunchDaemon (trợ lý đặc quyền/LaunchDaemon) không được mặc định cho M0/v0.1

Research (nghiên cứu) input stack cho thấy session-level `CGEventTap` không cần root, trong khi HID-entry tap cần root. Vì vậy distribution architecture (kiến trúc phân phối) không nên thêm privileged helper/LaunchDaemon chỉ để có một nơi chạy background (nền). Nếu kiến trúc sau này chọn HID seize/virtual-device path (đường chiếm HID/thiết bị ảo) hoặc một operation (thao tác) thực sự cần quyền hệ thống, helper topology (cấu trúc trợ lý) phải được quyết định và ký riêng.

Sources:
- https://developer.apple.com/documentation/coregraphics/cgevent/tapcreate(tap:place:options:eventsofinterest:callback:userinfo:)
- https://developer.apple.com/documentation/servicemanagement/smappservice

## Recommended distribution baseline (đường cơ sở phân phối khuyến nghị)

Cho M0 + v0.1, baseline (đường cơ sở) nên là:

1. Build `.app` với Swift/SwiftUI application shell (vỏ ứng dụng) và Rust core (lõi Rust) được link/embedded (liên kết/nhúng) theo architecture decision (quyết định kiến trúc).
2. Distribution build (bản dựng phân phối) dùng `Developer ID Application`.
3. Bật Hardened Runtime; chỉ khai báo entitlements thực sự cần.
4. Ký từng nested executable/code item (tệp thực thi/thành phần mã lồng nhau) từ trong ra ngoài; không dùng `codesign --deep` để ký.
5. Notarize bằng `notarytool` hoặc Xcode hiện hành, kiểm tra notary log (nhật ký công chứng), staple ticket (đính vé công chứng) khi artifact hỗ trợ.
6. Đóng signed/notarized app thành ZIP cho GitHub Release; project Homebrew Cask tap cài ZIP đó.
7. App không sandbox theo baseline; TCC permission onboarding (hướng dẫn quyền TCC) là runtime concern (mối quan tâm thời gian chạy) riêng.
8. Không thêm privileged helper/LaunchDaemon trong M0/v0.1 nếu architecture ticket không chứng minh cần thiết.
9. Nếu minimum deployment target (mục tiêu macOS tối thiểu) >= macOS 13, ưu tiên `SMAppService` cho launch-at-login/helper registration (đăng ký trợ lý). Nếu cần hỗ trợ macOS cũ hơn, phải có quyết định compatibility (tương thích) riêng thay vì vô tình tạo legacy path (đường cũ).

## Release gates (cổng phát hành) cần chuyển sang execution planning (lập kế hoạch thực thi)

M0 release pipeline (đường ống phát hành) phải có machine-checkable commands (lệnh kiểm tra bằng máy) cho ít nhất:

- xác minh distribution signing identity/signature (định danh/chữ ký phân phối),
- xác minh Hardened Runtime/entitlements (môi trường chạy tăng cường/quyền khai báo),
- submit/wait/log notarization (gửi/chờ/đọc nhật ký công chứng),
- staple + validate ticket khi áp dụng,
- cài artifact sạch qua project Homebrew Cask tap,
- launch/quit/relaunch và xác nhận fail-safe (cơ chế an toàn),
- upgrade/uninstall (nâng cấp/gỡ) không để lại helper/service (trợ lý/dịch vụ) ngoài ý muốn.

## Newly exposed decision (quyết định mới lộ ra)

Minimum macOS deployment target (mục tiêu macOS tối thiểu) giờ là một quyết định kiến trúc sắc nét, không còn là fog (vùng chưa rõ). Nó ảnh hưởng trực tiếp tới `SMAppService`, lựa chọn Core HID/IOHID (HID lõi/IOHID), Swift concurrency/API availability (đồng thời/khả dụng API Swift), test matrix (ma trận kiểm thử) và lượng compatibility code (mã tương thích). Phải resolve (giải quyết) trước khi khóa runtime topology (cấu trúc thời gian chạy).