import Platform
import XCTest

final class InputRuntimeTests: XCTestCase {
    func testRuntimeTransitionsFollowObservedTapStatus() {
        let runtime = InputRuntime()
        runtime.setEnabled(true)
        runtime.update(accessibilityTrusted: true, runtimeStatus: .active)
        XCTAssertEqual(runtime.state, .active)
        runtime.update(accessibilityTrusted: true, runtimeStatus: .unavailable)
        XCTAssertEqual(runtime.state, .inputUnavailable)
        runtime.setEnabled(false)
        XCTAssertEqual(runtime.state, .off)
        runtime.update(accessibilityTrusted: false, runtimeStatus: .unavailable)
        XCTAssertEqual(runtime.state, .off)
    }
}
