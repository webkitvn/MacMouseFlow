# macOS 14+ scroll-event semantics research — Phase 1 Scroll Feel Control

## Question

Trên baseline (đường cơ sở) macOS 14+, các documented public event-level contracts (hợp đồng cấp sự kiện công khai được tài liệu hóa) nào của Quartz Event Services / `CGEvent` / `NSEvent` đủ đáng tin để quyết định một user-visible `Scroll Configuration` (Cấu hình cuộn hiển thị) beyond direction (vượt quá hướng) cho `LineBased` `Scroll Event`, trong khi `PixelBased` input vẫn preserve-by-default (giữ nguyên mặc định) và current single-process event-level topology (cấu trúc một tiến trình cấp sự kiện hiện tại) vẫn fail-open (an toàn khi lỗi)?

Research này chỉ ghi facts/constraints (sự kiện/ràng buộc) và các inference (suy luận) được đánh dấu rõ. Nó không chọn UX control (điều khiển UX), thuật toán hay giá trị tuning (tinh chỉnh) sẽ ship.

## Findings

### 1. Core Graphics có discriminator (bộ phân biệt) công khai cho line-based so với pixel-based scroll

`CGEventField.scrollWheelEventIsContinuous` là field (trường) công khai. Apple document rằng giá trị khác 0 nghĩa là scrolling data (dữ liệu cuộn) continuous/pixel-based (liên tục/theo pixel), còn 0 nghĩa là line-based (theo dòng).

Đây là event characteristic (đặc tính sự kiện), không phải physical-device identity (định danh thiết bị vật lý). Không được suy từ `LineBased`/`PixelBased` thành Mouse/Trackpad `Source Class` hay `Device Identity`.

Sources:
- https://developer.apple.com/documentation/coregraphics/cgeventfield/scrollwheeleventiscontinuous
- https://developer.apple.com/documentation/coregraphics/cgeventfield
- upstream physical-device boundary: `docs/research/macos-input-stack.md`

### 2. Quartz exposes (cung cấp) nhiều biểu diễn scroll delta có kiểu và precision (độ chính xác) khác nhau

Apple document các `CGEventField` sau cho scroll:

- `scrollWheelEventDeltaAxis1` / `Axis2`: integer scrolling data (dữ liệu cuộn số nguyên), thường biểu diễn thay đổi vertical/horizontal (dọc/ngang) từ event trước.
- `scrollWheelEventFixedPtDeltaAxis1` / `Axis2`: line-based hoặc pixel-based delta ở fixed-point 16.16 (số cố định 16.16); khi đọc bằng floating-point accessor (bộ đọc dấu phẩy động), Core Graphics chuyển đổi sang `double`.
- `scrollWheelEventPointDeltaAxis1` / `Axis2`: integer pixel-based delta (delta theo pixel số nguyên).

`CGEventField` được dùng với cả integer và double get/set accessors (bộ đọc/ghi số nguyên và dấu phẩy động). `CGEventSetDoubleValueField` document rằng khi backing representation (biểu diễn nền) là fixed-point hoặc integer, giá trị truyền vào được scale/convert (co giãn/chuyển đổi) theo kiểu field.

Hệ quả cấp API: một event-level transform (biến đổi cấp sự kiện) có public surface (bề mặt công khai) để đọc và ghi scrolling magnitude (độ lớn cuộn); không cần HID chỉ để thay đổi delta của một Quartz scroll event.

Sources:
- https://developer.apple.com/documentation/coregraphics/cgeventfield
- https://developer.apple.com/documentation/coregraphics/cgeventfield/scrollwheeleventdeltaaxis1
- https://developer.apple.com/documentation/coregraphics/cgevent/setdoublevaluefield(_:value:)

### 3. AppKit có preferred scroll deltas (delta cuộn ưu tiên) và precise/coarse semantics (ngữ nghĩa chính xác/thô), nhưng precise không phải device identity

Apple document `NSEvent.scrollingDeltaX` / `scrollingDeltaY` là preferred properties (thuộc tính ưu tiên) cho `NSScrollWheel` delta. Khi `hasPreciseScrollingDeltas == false`, application có thể cần scale (co giãn) giá trị theo line/row height (chiều cao dòng/hàng); khi precise delta có sẵn thì ứng dụng có thể dùng returned amount (lượng trả về) trực tiếp theo semantics của AppKit.

Apple cũng nói generic scroll wheel (bánh xe cuộn thông thường) thường tạo coarse delta (delta thô), trong khi một số mice và trackpads có precise delta (delta chính xác). Vì cả mouse lẫn trackpad có thể nằm trong tập precise, `hasPreciseScrollingDeltas` chỉ là precision characteristic (đặc tính độ chính xác), không phải Source Class hay `Device Identity`.

Sources:
- https://developer.apple.com/documentation/appkit/nsevent/scrollingdeltax
- https://developer.apple.com/documentation/appkit/nsevent/scrollingdeltay
- https://developer.apple.com/documentation/appkit/nsevent/hasprecisescrollingdeltas

### 4. Line/pixel units (đơn vị dòng/pixel) là public Quartz concept (khái niệm Quartz công khai)

`CGScrollEventUnit` có hai unit (đơn vị) công khai: `.line` và `.pixel`. `CGEventCreateScrollWheelEvent` có thể tạo Quartz scroll event theo một trong hai unit này.

Apple document rằng pixel-unit event thường được ứng dụng diễn giải như smooth scrolling (cuộn mượt). `CGEventSource` cũng có pixels-per-line scale (tỉ lệ pixel trên dòng): Core Graphics có get/set API để lấy hoặc đặt số pixel tương ứng một line trên event source; default được Apple mô tả xấp xỉ 10 pixels/line.

Đây là conversion/representation contract (hợp đồng chuyển đổi/biểu diễn), không phải recommendation (khuyến nghị) rằng product nên expose `pixelsPerLine` trực tiếp cho user.

Sources:
- https://developer.apple.com/documentation/coregraphics/cgscrolleventunit
- https://developer.apple.com/documentation/coregraphics/cgeventcreatescrollwheelevent
- https://developer.apple.com/documentation/coregraphics/cgeventsourcesetpixelsperline
- https://developer.apple.com/documentation/coregraphics/cgeventsource/pixelsperline

### 5. Active event tap (điểm chặn sự kiện chủ động) có documented mutation/replacement contract (hợp đồng sửa/thay thế)

Apple document rằng callback của active event tap có thể:

- trả lại chính incoming event (sự kiện vào), kể cả sau khi đã sửa;
- trả lại một newly constructed event (sự kiện mới tạo);
- trả `NULL` để xóa event.

Vì Core Graphics cũng có public setters cho specialized event fields (trường sự kiện chuyên biệt), một stateless transform (biến đổi không trạng thái) như bounded scaling (co giãn có giới hạn) của `LineBased` delta có thể ở cùng session event-tap callback path (đường callback event tap cấp phiên) và trả event đã sửa, không cần post một synthetic event (sự kiện tổng hợp) mới chỉ để đổi magnitude (độ lớn).

Sources:
- https://developer.apple.com/documentation/coregraphics/cgeventtapcallback
- https://developer.apple.com/documentation/coregraphics/cgeventfield
- https://developer.apple.com/documentation/coregraphics/cgevent/setdoublevaluefield(_:value:)

### 6. Synthetic posting (phát sự kiện tổng hợp) là public API nhưng có graph/recursion implications (hệ quả đồ thị/đệ quy)

`CGEventPost` đăng một Quartz event vào event stream (luồng sự kiện) tại một tap location (vị trí điểm chặn) cụ thể. Apple document rằng event được post ngay trước các event taps ở location đó và sẽ đi qua các taps đó.

Hệ quả: nếu một future stateful smoother/momentum synthesizer (bộ làm mượt/tổng hợp quán tính có trạng thái tương lai) tạo và post event mới, implementation phải có explicit loop/ownership strategy (chiến lược vòng lặp/quyền sở hữu rõ) để không tự xử lý lại event của chính mình ngoài ý muốn. Research này không chọn strategy đó.

Source:
- https://developer.apple.com/documentation/coregraphics/cgevent/post(tap:)

### 7. Gesture phase (pha cử chỉ) và momentum phase (pha quán tính) tồn tại công khai, nhưng không áp dụng đồng đều cho mọi scroll stream

`NSEvent.phase` mô tả phase của fluid gesture event (sự kiện cử chỉ liên tục), gồm began/changed/ended/cancelled/mayBegin/stationary/none (bắt đầu/thay đổi/kết thúc/hủy/có thể bắt đầu/đứng yên/không có).

Apple document các điểm quan trọng:

- gesture scroll event (sự kiện cuộn dạng cử chỉ) có lifecycle (vòng đời) bắt đầu và kết thúc;
- trackpad có thể phát `mayBegin` trước khi gesture chính thức bắt đầu;
- Magic Mouse không phát `mayBegin` scroll-wheel event;
- legacy scroll-wheel event có `phase == none`;
- momentum scroll-wheel event cũng có normal `phase == none` và dùng `momentumPhase` riêng.

`NSEvent.momentumPhase` là public property cho scroll/flick gesture (cử chỉ cuộn/vẩy); Apple mô tả một số devices có thể tạo stream scroll events giảm dần theo thời gian.

Vì vậy phase/momentum metadata (siêu dữ liệu pha/quán tính) là hữu ích để nhận biết một số temporal streams (luồng thời gian), nhưng không thể làm invariant (bất biến) rằng mọi `LineBased` scroll event luôn có phase lifecycle đầy đủ.

Sources:
- https://developer.apple.com/documentation/appkit/nsevent/phase-swift.property
- https://developer.apple.com/documentation/appkit/nsevent/phase-swift.struct
- https://developer.apple.com/documentation/appkit/nsevent/momentumphase

### 8. Low-level Core Graphics có scroll/momentum phase fields, nhưng public pages được đọc không document semantics đủ sâu để làm correctness contract (hợp đồng tính đúng)

`CGEventField` công khai tên các fields như `scrollWheelEventMomentumPhase`, `scrollWheelEventScrollPhase` và `scrollWheelEventScrollCount`; Core Graphics cũng công khai `CGMomentumScrollPhase` enumeration (liệt kê pha quán tính).

Tuy nhiên các Apple documentation pages được đọc cho low-level phase fields chủ yếu xác nhận symbol (ký hiệu) tồn tại mà không giải thích mapping/value semantics (ngữ nghĩa ánh xạ/giá trị) chi tiết tương đương `NSEvent.phase` / `momentumPhase`.

Do đó research này không dùng raw integer values (giá trị số nguyên thô) của các fields đó làm project correctness contract. Nếu một decision sau muốn dựa trực tiếp vào low-level phase fields trong Rust/native ABI, phải xác minh semantic mapping (ánh xạ ngữ nghĩa) bằng SDK headers/primary documentation và execution observations riêng trước khi khóa contract.

Sources:
- https://developer.apple.com/documentation/coregraphics/cgeventfield
- https://developer.apple.com/documentation/coregraphics/cgeventfield/scrollwheeleventmomentumphase
- https://developer.apple.com/documentation/coregraphics/cgmomentumscrollphase

### 9. `NSEvent` có public bridge (cầu nối công khai) từ `CGEvent`

AppKit document `NSEvent.init?(cgEvent:)`, tạo một Cocoa event tương đương từ `CGEvent` khi conversion (chuyển đổi) khả thi. Điều này cho phép native layer (tầng bản địa) trong cùng process (tiến trình) đọc documented AppKit scroll properties (thuộc tính cuộn AppKit được tài liệu hóa) từ một Quartz event mà không tự nó buộc phải thêm helper/IPC/process (tiến trình phụ/IPC/tiến trình mới).

Research này không khẳng định mọi event tap `CGEvent` sẽ luôn convert thành `NSEvent` với mọi phase field có ý nghĩa; initializer có thể trả `nil` nếu không có Cocoa equivalent (tương đương Cocoa). Đây là execution/prototype point (điểm cần thực thi/nguyên mẫu), không phải lý do để đổi architecture ngay.

Sources:
- https://developer.apple.com/documentation/appkit/nsevent/init(cgevent:)-4igjn
- https://developer.apple.com/documentation/appkit/nsevent/cgevent

### 10. Direction inversion state (trạng thái đảo hướng) là user-preference semantics (ngữ nghĩa tùy chọn người dùng), không phải source identity

`NSEvent.isDirectionInvertedFromDevice` cho biết scrolling direction (hướng cuộn) đã bị đảo theo user preference (tùy chọn người dùng) hay chưa. Apple document rằng các delta properties của scroll-wheel event đã được automatically inverted (tự động đảo) theo preference.

Điều này có nghĩa direction semantics (ngữ nghĩa hướng) và magnitude/feel semantics (ngữ nghĩa độ lớn/cảm giác) cần được tách rõ trong product/domain decision: Phase 1 không nên vô tình double-invert (đảo hai lần) chỉ vì đang scale delta.

Source:
- https://developer.apple.com/documentation/appkit/nsevent/isdirectioninvertedfromdevice

### 11. Event tap vẫn là realtime-sensitive boundary (ranh giới nhạy thời gian thực)

Apple có `CGEventType.tapDisabledByTimeout`, tức event tap có thể bị hệ thống disable (tắt) do timeout. `CGEventTapCreate` phân biệt passive listener (bộ nghe thụ động) với active filter (bộ lọc chủ động); HID-entry location (vị trí đầu vào HID) yêu cầu process chạy root, trong khi session-level event tap không có ràng buộc root đó.

Project đã có stricter internal latency/reliability gates (cổng độ trễ/độ tin cậy nội bộ nghiêm hơn) từ baseline. Research mới không tìm thấy public fact nào cho phép nới các gate đó.

Sources:
- https://developer.apple.com/documentation/coregraphics/cgeventtype/tapdisabledbytimeout
- https://developer.apple.com/documentation/coregraphics/cgevent/tapcreate(tap:place:options:eventsofinterest:callback:userinfo:)

### 12. Permission APIs (API quyền) vẫn tồn tại, nhưng Phase 1 không cần phát minh permission model mới chỉ để scale line deltas

Core Graphics hiện có listen/post preflight APIs (API kiểm tra trước quyền nghe/phát). Existing project baseline đã model permission/runtime availability (mô hình hóa quyền/khả năng runtime) thành explicit state (trạng thái rõ ràng).

Research này không tìm thấy fact nào cho thấy bounded modification (sửa có giới hạn) của event trên current session active-filter path cần một loại permission architecture (kiến trúc quyền) mới chỉ vì magnitude (độ lớn) được thay đổi thay vì direction (hướng).

Sources:
- https://developer.apple.com/documentation/coregraphics/cgpreflightlisteneventaccess()
- https://developer.apple.com/documentation/coregraphics/cgpreflightposteventaccess()
- upstream permission analysis: `docs/research/macos-input-stack.md`

## Stateless vs stateful capability boundary (ranh giới khả năng không trạng thái / có trạng thái)

### Directly supported by documented contracts (được hợp đồng công khai hỗ trợ trực tiếp)

Một **stateless `LineBased` magnitude transform (biến đổi độ lớn theo dòng không trạng thái)** có nền tảng API rõ:

1. classify (phân loại) line-based vs pixel-based bằng `scrollWheelEventIsContinuous`;
2. preserve (giữ nguyên) pixel-based events;
3. đọc line-based delta qua public fields;
4. áp bounded deterministic function (hàm xác định có giới hạn) lên magnitude/sign (độ lớn/dấu) theo `Scroll Configuration` đã validate (xác thực);
5. ghi field trở lại và return modified event (trả event đã sửa) qua active event tap.

Đây là API capability statement (tuyên bố khả năng API), không phải product decision rằng multiplier/sensitivity control (điều khiển hệ số/độ nhạy) chắc chắn sẽ ship.

### Plausible but requires explicit decision/prototype (khả thi về mặt API nhưng cần quyết định/nguyên mẫu riêng)

**Stateful acceleration (gia tốc có trạng thái)** có thể lưu bounded state (trạng thái có giới hạn) trong current process và biến đổi event stream, nhưng Apple documentation không định nghĩa project acceleration curve (đường cong gia tốc), reset boundary (ranh giới reset), cancellation semantics (ngữ nghĩa hủy), hay expected behavior (hành vi mong đợi) giữa ứng dụng. Đây là product/domain/state-machine decision (quyết định sản phẩm/miền/máy trạng thái), không phải fact từ API.

**Smoothing/momentum synthesis (làm mượt/tổng hợp quán tính)** còn phức tạp hơn: nó có thể cần buffering/scheduling (đệm/lập lịch), tạo/post events sau input event ban đầu, quản lý cancellation/ownership (hủy/quyền sở hữu) và tránh synthetic-event feedback loop (vòng phản hồi sự kiện tổng hợp). Public APIs cho phép tạo/post scroll events và expose phase/momentum metadata, nhưng research không tìm thấy public contract bảo đảm một synthesized stream (luồng tổng hợp) sẽ tương đương system-native momentum behavior (hành vi quán tính bản địa hệ thống) trong mọi ứng dụng.

Vì vậy smoothing/momentum synthesis không nên được coi là automatic extension (mở rộng tự động) của stateless scaling.

## Party Meeting — competing interpretations (cuộc họp phản biện — các cách diễn giải cạnh tranh)

### Position A — Product breadth (độ rộng sản phẩm)

Phase 1 nên tận dụng phase/momentum metadata để tạo khác biệt cảm giác rõ rệt; chỉ multiplier (hệ số) có thể quá nhỏ về user value (giá trị người dùng).

**Strong point (điểm mạnh):** Apple expose phase/momentum public data và synthetic scroll creation/posting, nên event-level path không bị giới hạn tuyệt đối vào một phép nhân delta.

**Weak point (điểm yếu):** API existence (sự tồn tại API) không định nghĩa product semantics (ngữ nghĩa sản phẩm) hoặc guarantee native-equivalent synthesized momentum (bảo đảm quán tính tổng hợp tương đương bản địa).

### Position B — Realtime reliability (độ tin cậy thời gian thực)

Phase 1 chỉ nên xem stateless magnitude transform là proven-safe candidate family (họ ứng viên đã có nền API rõ), vì event tap là hot path (đường nóng), có timeout-disable, và synthetic posting đi qua event taps.

**Strong point:** giảm state/latency/recursion/cancellation risk (rủi ro trạng thái/độ trễ/đệ quy/hủy), giữ fail-open đơn giản.

**Weak point:** nếu quá bảo thủ có thể ship một capability ít cải thiện cảm giác thực tế; API facts không chứng minh stateful acceleration là không thể.

### Position C — Contract-first middle position (vị trí giữa ưu tiên hợp đồng)

Chốt research boundary, không chốt product: stateless `LineBased` magnitude transform là directly supported candidate (ứng viên được hỗ trợ trực tiếp); stateful acceleration vẫn in-scope fog (sương mù trong phạm vi) nếu user outcome cần; smoothing/momentum synthesis đòi explicit state-machine/prototype/latency decision (quyết định máy trạng thái/nguyên mẫu/độ trễ rõ ràng).

**Research conclusion:** Position C phù hợp nhất với facts. Nó không biến API capability thành requirement (yêu cầu), và cũng không loại stateful behavior chỉ vì phức tạp.

## Architecture implications (hệ quả kiến trúc)

### No architecture change is proven necessary for a meaningful Phase 1

Không có primary-source fact nào trong research này chứng minh Phase 1 bắt buộc phải thêm HID path, helper/IPC, process mới hoặc physical-device correlation để cung cấp một meaningful `LineBased` scroll-control capability (khả năng điều khiển cuộn theo dòng có ý nghĩa).

Current single-process native event adapter + narrow ABI + engine topology vẫn đủ ở mức capability để làm bounded stateless delta transforms; `NSEvent` bridge cũng tồn tại nếu native layer cần đọc documented AppKit properties.

### Architecture change is not ruled out for a future stronger semantics

Nếu product decision sau yêu cầu synthetic momentum/smoothing fidelity (độ trung thực làm mượt/quán tính tổng hợp), per-device behavior, hoặc semantics cần data/current topology không cung cấp đáng tin, lúc đó phải mở explicit superseding architecture decision (quyết định kiến trúc thay thế rõ ràng). Research này không chứng minh nhu cầu đó ở Phase 1.

## macOS 14+ baseline note (ghi chú đường cơ sở)

Research này không dựa vào Core HID, helper API hay một API được chọn chỉ vì xuất hiện ở macOS mới hơn baseline. Các candidate contracts được dùng đều là Quartz/AppKit event-level surfaces (bề mặt cấp sự kiện Quartz/AppKit) đã nằm trong architecture family (họ kiến trúc) của baseline hiện tại.

Artifact này **không claim exact introduction version (không tuyên bố phiên bản giới thiệu chính xác)** cho từng symbol khi Apple page được đọc không expose availability metadata (siêu dữ liệu khả dụng) trong nội dung thu được. Nếu một implementation proposal (đề xuất triển khai) sau dựa vào symbol mà availability cho macOS 14 còn nghi ngờ, execution/planning phải xác minh trực tiếp bằng target SDK (SDK mục tiêu) trước khi dùng nó làm contract.

## Decision inputs unlocked (đầu vào quyết định được mở khóa)

Research đủ để ticket product/domain semantics (ngữ nghĩa sản phẩm/miền) kế tiếp hỏi một câu sắc hơn:

> Với `LineBased` stateless magnitude transform đã có documented event-level support (hỗ trợ cấp sự kiện được tài liệu hóa), Phase 1 nên expose user outcome nhỏ nhất nào beyond direction — fixed speed/multiplier/sensitivity semantics (ngữ nghĩa tốc độ/hệ số/độ nhạy cố định), hay có đủ giá trị để mở stateful acceleration — trong khi smoothing/momentum synthesis chỉ được mở nếu một prototype/state-machine decision chứng minh cần?

Research chưa đủ để quyết định câu trả lời đó; nó chỉ loại bỏ nhu cầu phải nghiên cứu toàn bộ HID/device stack trước khi hỏi product semantics.

## Primary sources index (chỉ mục nguồn sơ cấp)

- Core Graphics `CGEventField`: https://developer.apple.com/documentation/coregraphics/cgeventfield
- `scrollWheelEventIsContinuous`: https://developer.apple.com/documentation/coregraphics/cgeventfield/scrollwheeleventiscontinuous
- `CGEventSetDoubleValueField`: https://developer.apple.com/documentation/coregraphics/cgevent/setdoublevaluefield(_:value:)
- `CGEventTapCallBack`: https://developer.apple.com/documentation/coregraphics/cgeventtapcallback
- `CGEventTapCreate`: https://developer.apple.com/documentation/coregraphics/cgevent/tapcreate(tap:place:options:eventsofinterest:callback:userinfo:)
- `tapDisabledByTimeout`: https://developer.apple.com/documentation/coregraphics/cgeventtype/tapdisabledbytimeout
- `CGScrollEventUnit`: https://developer.apple.com/documentation/coregraphics/cgscrolleventunit
- `CGEventCreateScrollWheelEvent`: https://developer.apple.com/documentation/coregraphics/cgeventcreatescrollwheelevent
- `CGEventSourceSetPixelsPerLine`: https://developer.apple.com/documentation/coregraphics/cgeventsourcesetpixelsperline
- `CGEventPost`: https://developer.apple.com/documentation/coregraphics/cgevent/post(tap:)
- AppKit `NSEvent.hasPreciseScrollingDeltas`: https://developer.apple.com/documentation/appkit/nsevent/hasprecisescrollingdeltas
- `NSEvent.scrollingDeltaX`: https://developer.apple.com/documentation/appkit/nsevent/scrollingdeltax
- `NSEvent.scrollingDeltaY`: https://developer.apple.com/documentation/appkit/nsevent/scrollingdeltay
- `NSEvent.phase`: https://developer.apple.com/documentation/appkit/nsevent/phase-swift.property
- `NSEvent.momentumPhase`: https://developer.apple.com/documentation/appkit/nsevent/momentumphase
- `NSEvent.init(cgEvent:)`: https://developer.apple.com/documentation/appkit/nsevent/init(cgevent:)-4igjn
- `NSEvent.isDirectionInvertedFromDevice`: https://developer.apple.com/documentation/appkit/nsevent/isdirectioninvertedfromdevice
- `CGPreflightListenEventAccess`: https://developer.apple.com/documentation/coregraphics/cgpreflightlisteneventaccess()
- `CGPreflightPostEventAccess`: https://developer.apple.com/documentation/coregraphics/cgpreflightposteventaccess()
