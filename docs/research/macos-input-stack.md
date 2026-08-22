# macOS input stack research

## Question

Public macOS APIs (API công khai của macOS) nào phù hợp để quan sát, chặn, biến đổi và phát lại mouse input (đầu vào chuột), và các ràng buộc về permission (quyền), sandbox (hộp cát), device identity (định danh thiết bị) và latency (độ trễ) ảnh hưởng thế nào tới boundary (ranh giới) giữa native layer (lớp bản địa) và core engine (bộ máy lõi)?

## Findings

### 1. Quartz Event Services phù hợp cho system event transform (biến đổi sự kiện hệ thống)

Apple mô tả Quartz Event Services là API quản lý event taps (điểm chặn sự kiện), cho phép quan sát và thay đổi low-level user input events (sự kiện đầu vào mức thấp) trước khi chúng tới foreground application (ứng dụng tiền cảnh). Active event filter (bộ lọc sự kiện chủ động) có thể trả lại event đã sửa, event mới, hoặc `NULL` để loại bỏ event. `CGEventPost` có thể đăng một Quartz event trở lại event stream (luồng sự kiện).

Sources:
- https://developer.apple.com/documentation/coregraphics/quartz-event-services
- https://developer.apple.com/documentation/coregraphics/cgeventtapcallback
- https://developer.apple.com/documentation/coregraphics/cgevent/post(tap:)

`CGEventTapLocation` có ba điểm chính: HID event tap (điểm chặn HID), session event tap (điểm chặn phiên đăng nhập), và annotated session event tap (điểm chặn phiên đã chú giải). Apple ghi rõ chỉ process chạy root (tiến trình quyền root) mới đặt event tap tại điểm HID events đi vào WindowServer; vì vậy kiến trúc không nên phụ thuộc vào `cghidEventTap` nếu mục tiêu là ứng dụng người dùng bình thường không cần root.

Sources:
- https://developer.apple.com/documentation/coregraphics/cgeventtaplocation
- https://developer.apple.com/documentation/coregraphics/cgevent/tapcreate(tap:place:options:eventsofinterest:callback:userinfo:)

### 2. Event-tap callback là hot path (đường xử lý nóng), không được làm công việc không giới hạn

Apple định nghĩa event tap callback (hàm gọi lại của điểm chặn) chạy từ run loop (vòng lặp chạy) mà tap được gắn vào. Apple cũng có event type `tapDisabledByTimeout` và cho phép re-enable (bật lại) tap khi nó trở nên unresponsive (không phản hồi). Không có numeric latency budget (ngân sách độ trễ bằng số) trong các tài liệu đã đọc, nhưng API contract (hợp đồng API) cho thấy callback phải ngắn, bounded (có giới hạn) và không chứa UI, disk I/O (I/O đĩa), synchronous logging (ghi log đồng bộ), network (mạng), hoặc công việc blocking (chặn luồng).

Sources:
- https://developer.apple.com/documentation/coregraphics/cgeventtapcallback
- https://developer.apple.com/documentation/coregraphics/cgeventtype/tapdisabledbytimeout
- https://developer.apple.com/documentation/coregraphics/cgevent/tapenable(tap:enable:)

### 3. Public CGEvent/NSEvent không cung cấp physical device identity (định danh thiết bị vật lý) đáng tin cậy cho mouse/scroll thông thường

`CGEventField` công khai các trường mouse/scroll như button number (số nút), mouse delta (độ dịch chuyển chuột), scroll delta (độ dịch chuyển cuộn) và source process/user fields (trường tiến trình/người dùng nguồn), nhưng không có general mouse physical-device ID (ID thiết bị chuột vật lý tổng quát). `tabletEventDeviceID` chỉ dành cho tablet data (dữ liệu bảng vẽ).

Ở AppKit, `NSEvent.deviceID` cũng chỉ hợp lệ cho tablet pointer/proximity events (sự kiện con trỏ/tiệm cận bảng vẽ), không phải generic scroll event (sự kiện cuộn tổng quát). `hasPreciseScrollingDeltas` chỉ nói delta có độ chính xác cao hay không; Apple nêu generic scroll wheel thường coarse (thô), còn một số mice và trackpads có precise deltas (độ dịch chuyển chính xác). Vì vậy precise/coarse chỉ là characteristic (đặc tính), không phải device identity (định danh thiết bị).

Consequence (hệ quả): không nên thiết kế v0.1 với giả định một `CGEvent` scroll event tự nó cho biết chắc chắn event đến từ built-in trackpad (bàn di chuột tích hợp) hay external mouse (chuột ngoài).

Sources:
- https://developer.apple.com/documentation/coregraphics/cgeventfield
- https://developer.apple.com/documentation/coregraphics/cgeventfield/tableteventdeviceid
- https://developer.apple.com/documentation/appkit/nsevent/deviceid
- https://developer.apple.com/documentation/appkit/nsevent/hasprecisescrollingdeltas

### 4. HID layer (lớp HID) cung cấp device identity và raw input (đầu vào thô)

`IOHIDManager` là public IOKit API (API IOKit công khai) để quản lý HID devices (thiết bị HID). Nó có device matching (đối sánh thiết bị), device arrival/removal callbacks (hàm gọi lại thêm/gỡ thiết bị), input value callbacks (hàm gọi lại giá trị đầu vào) và input report callbacks (hàm gọi lại báo cáo đầu vào). Device properties (thuộc tính thiết bị) gồm vendor ID, product ID, transport, usage/usage pages và các metadata khác.

Apple lưu ý `PrimaryUsage`/`PrimaryUsagePage` không luôn đủ cho composite device (thiết bị tổng hợp), và cung cấp `DeviceUsage`, `DeviceUsagePage`, `DeviceUsagePairs` để mô tả nhiều behavior (hành vi) của cùng một HID.

Sources:
- https://developer.apple.com/documentation/iokit/1438383-iohidmanagercreate
- https://developer.apple.com/documentation/iokit/1438367-iohidmanagerregisterinputvalueca
- https://developer.apple.com/documentation/iokit/kiohiddeviceusagepairskey
- https://developer.apple.com/documentation/iokit/kiohidvendoridkey
- https://developer.apple.com/documentation/iokit/kiohidproductidkey
- https://developer.apple.com/documentation/iokit/kiohidtransportkey

### 5. Core HID là Swift-native HID surface (bề mặt HID bản địa cho Swift) đáng đánh giá nếu deployment target (mục tiêu hệ điều hành) cho phép

Core HID cung cấp `HIDDeviceManager`, `HIDDeviceClient`, strongly typed HID usages (usage HID có kiểu rõ), async streams (luồng bất đồng bộ), raw input reports (báo cáo đầu vào thô), element updates (cập nhật phần tử), device metadata và `isBuiltIn` để phân biệt built-in peripheral (thiết bị tích hợp) với external peripheral (thiết bị ngoài). `HIDDeviceClient.seizeDevice()` có thể cố lấy exclusive access (quyền truy cập độc quyền) vào thiết bị; `HIDVirtualDevice` có thể tạo virtual HID device (thiết bị HID ảo) và dispatch input reports (phát báo cáo đầu vào) vào hệ thống.

Virtual HID cần entitlement (quyền khai báo) `com.apple.developer.hid.virtual.device` theo tài liệu entitlement của Apple.

Sources:
- https://developer.apple.com/documentation/corehid
- https://developer.apple.com/documentation/corehid/communicatingwithhiddevices
- https://developer.apple.com/documentation/corehid/hiddeviceclient/seizedevice()
- https://developer.apple.com/documentation/corehid/creatingvirtualdevices
- https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.hid.virtual.device

Open constraint (ràng buộc còn mở): deployment availability (khả dụng theo phiên bản hệ điều hành) của Core HID phải được xác minh trực tiếp bằng target SDK/Xcode trước khi dùng làm nền tảng. Không lấy availability từ nguồn thứ ba làm quyết định kiến trúc.

### 6. Permission model (mô hình quyền) phải là state (trạng thái) hạng nhất của ứng dụng

Apple mô tả Input Monitoring (Giám sát đầu vào) là quyền cho phép app theo dõi keyboard, mouse hoặc trackpad ngay cả khi người dùng đang dùng ứng dụng khác. Accessibility (Trợ năng) cho phép ứng dụng được cấp quyền truy cập/control (điều khiển) Mac qua accessibility features (tính năng trợ năng).

Core Graphics có preflight/request APIs (API kiểm tra/yêu cầu) cho listen/post event access (quyền nghe/phát sự kiện); tài liệu hiện tại đánh dấu các request functions (hàm yêu cầu) trong danh sách Core Graphics functions là deprecated (không khuyến nghị dùng mới), nên onboarding (hướng dẫn cấp quyền) không nên phụ thuộc duy nhất vào một request helper (hàm trợ giúp yêu cầu quyền) mà phải quan sát trạng thái thật và hướng người dùng tới System Settings khi cần.

Sources:
- https://support.apple.com/guide/mac-help/mchl4cedafb6/mac
- https://support.apple.com/guide/mac-help/mh43185/mac
- https://developer.apple.com/documentation/coregraphics/cgpreflightlisteneventaccess()
- https://developer.apple.com/documentation/coregraphics/cgpreflightposteventaccess()
- https://developer.apple.com/documentation/coregraphics/core-graphics-functions
- https://developer.apple.com/documentation/applicationservices/1459186-axisprocesstrustedwithoptions

### 7. App Sandbox không nên được mặc định là khả thi cho runtime can thiệp input

Apple yêu cầu App Sandbox cho Mac App Store distribution (phân phối Mac App Store), nhưng tài liệu App Sandbox liệt kê việc dùng accessibility APIs trong assistive apps (API trợ năng trong ứng dụng hỗ trợ) là activity incompatible with App Sandbox (hoạt động không tương thích với hộp cát). Vì runtime mục tiêu cần monitor/filter/control system input (giám sát/lọc/điều khiển đầu vào hệ thống), kiến trúc không nên mặc định Mac App Store sandbox là đường phân phối khả thi. Ticket distribution (phân phối) phải chốt việc này cùng signing/notarization (ký mã/công chứng).

Sources:
- https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox
- https://developer.apple.com/documentation/security/app-sandbox

## Architecture implications (hệ quả kiến trúc)

### Candidate A — Session CGEventTap transform (biến đổi bằng event tap ở phiên)

Ưu điểm:
- Public API (API công khai), trực tiếp filter/modify/drop system events (lọc/sửa/bỏ sự kiện hệ thống).
- Không cần root nếu dùng session-level tapping point (điểm chặn cấp phiên) thay vì HID-entry point (điểm vào HID).
- Phù hợp với hot-path engine (bộ máy đường nóng) nhỏ và deterministic (xác định).

Nhược điểm:
- Không có physical device identity (định danh thiết bị vật lý) công khai cho generic scroll event.
- Không đủ một mình để đảm bảo scroll direction (hướng cuộn) khác nhau theo từng thiết bị.

### Candidate B — HID observe/classify + CGEventTap transform (HID quan sát/phân loại + event tap biến đổi)

Ưu điểm:
- HID layer biết danh sách thiết bị, metadata, connect/disconnect (kết nối/ngắt kết nối).
- Event tap vẫn là đường biến đổi hệ thống đơn giản.

Nhược điểm:
- Không có documented public key (khóa công khai được tài liệu hóa) nối một generic CG scroll event với HID device đã phát nó.
- Timestamp correlation (tương quan dấu thời gian) giữa HID và CGEvent nếu dùng làm source identity sẽ là heuristic (suy đoán), không nên trở thành correctness boundary (ranh giới đúng/sai) cho v0.1.

### Candidate C — Per-device HID capture/seize → transform → virtual/system output (thu/giữ HID theo thiết bị → biến đổi → đầu ra ảo/hệ thống)

Ưu điểm:
- Device identity (định danh thiết bị) là explicit (rõ ràng) ngay từ đầu.
- Có đường công khai để nhận raw report (báo cáo thô), exclusive access (truy cập độc quyền) và, với Core HID, tạo virtual HID output (đầu ra HID ảo).

Nhược điểm:
- Complexity/risk (độ phức tạp/rủi ro) cao hơn nhiều: HID descriptors (bộ mô tả HID), seizing behavior (hành vi chiếm thiết bị), virtual-device entitlement (quyền thiết bị ảo), compatibility (tương thích), fail-safe (cơ chế an toàn) và deployment target (mục tiêu hệ điều hành).
- Không nên chọn chỉ để làm v0.1 nếu một public event-level solution (giải pháp cấp sự kiện công khai) đủ cho outcome (kết quả) nhỏ hơn.

## Recommendation to the architecture ticket (khuyến nghị cho ticket kiến trúc)

1. Giữ Quartz Event Services / session `CGEventTap` là candidate (ứng viên) mặc định cho system event transformation (biến đổi sự kiện hệ thống).
2. Đặt CGEvent callback trên dedicated non-UI run loop/thread (vòng lặp/luồng riêng không phải UI); callback chỉ normalize tối thiểu → gọi deterministic engine seam (điểm nối bộ máy xác định) → trả event. Logging (ghi nhật ký) phải asynchronous/buffered (bất đồng bộ/có bộ đệm) ngoài callback.
3. Dùng HID APIs cho device discovery/capability (khám phá/khả năng thiết bị), nhưng không giả định có mapping công khai từ HID device tới generic CGEvent.
4. Với v0.1 independent mouse-vs-trackpad scroll (cuộn chuột-bàn di chuột độc lập), phải chọn rõ một trong hai: (a) chấp nhận documented characteristic heuristic (suy đoán dựa đặc tính được tài liệu hóa) và giới hạn outcome, hoặc (b) chọn HID-level per-device architecture (kiến trúc theo thiết bị ở tầng HID). Không được ghi requirement như thể CGEvent tự cung cấp device ID.
5. Không đưa root helper (trợ lý quyền root), DriverKit driver (trình điều khiển DriverKit), hoặc virtual HID architecture (kiến trúc HID ảo) vào M0/v0.1 nếu chưa có decision ticket (ticket quyết định) chứng minh nó cần thiết.
6. Coi permission state (trạng thái quyền), tap-disabled recovery (phục hồi khi điểm chặn bị tắt), device disconnect (ngắt thiết bị) và app crash/quit fail-safe (an toàn khi ứng dụng sập/thoát) là acceptance behavior (hành vi chấp nhận), không phải implementation detail (chi tiết triển khai).

## Research boundary (ranh giới nghiên cứu)

Tài liệu Apple xác nhận các primitive (nguyên thủy) ở trên nhưng không cung cấp numeric latency guarantee (bảo đảm độ trễ bằng số), cũng không tài liệu hóa một mapping generic CGEvent → physical HID device (ánh xạ CGEvent tổng quát → thiết bị HID vật lý). Hai điểm này phải được xử lý bằng architecture decision + benchmark/prototype (quyết định kiến trúc + đo chuẩn/nguyên mẫu), không được suy diễn thành fact (sự thật).