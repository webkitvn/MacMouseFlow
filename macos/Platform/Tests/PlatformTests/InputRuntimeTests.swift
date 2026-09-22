import Platform
import XCTest

final class InputRuntimeTests: XCTestCase {
    func testStateResolutionContract() {
        XCTAssertEqual(InputRuntimeState.resolve(enabled: false, accessibilityTrusted: true, runtimeStatus: .active), .off)
        XCTAssertEqual(InputRuntimeState.resolve(enabled: false, accessibilityTrusted: false, runtimeStatus: .unavailable), .off)
        XCTAssertEqual(InputRuntimeState.resolve(enabled: true, accessibilityTrusted: false, runtimeStatus: .active), .needsAccessibilityAccess)
        XCTAssertEqual(InputRuntimeState.resolve(enabled: true, accessibilityTrusted: false, runtimeStatus: .unavailable), .needsAccessibilityAccess)
        XCTAssertEqual(InputRuntimeState.resolve(enabled: true, accessibilityTrusted: true, runtimeStatus: .active), .active)
        XCTAssertEqual(InputRuntimeState.resolve(enabled: true, accessibilityTrusted: true, runtimeStatus: .unavailable), .inputUnavailable)
    }

    func testEnablingPublishesTruthfulNonActiveStateSynchronously() {
        let runtime = InputRuntime()
        runtime.setEnabled(true)
        // Intent is recorded and published on the caller's thread; lifecycle work runs
        // on the executor, so a successful start cannot already be observable here.
        XCTAssertNotEqual(runtime.state, .active)
        XCTAssertNotEqual(runtime.state, .off)
        runtime.setEnabled(false)
    }

    func testDisablePublishesOffWithoutApprovalFromLifecycleExecutor() {
        let runtime = InputRuntime()
        runtime.setEnabled(true)
        runtime.setEnabled(false)
        XCTAssertEqual(runtime.state, .off)

        runtime.refresh()
        XCTAssertEqual(runtime.state, .off)
    }

    func testReleasingRuntimeDoesNotBlockOrPoisonSubsequentRuntimes() {
        // Exercises the executor teardown submission path from a public seam: releasing
        // an enabled runtime must return on the caller's thread, and a replacement
        // runtime must be independently usable afterwards.
        var retiring: InputRuntime? = InputRuntime()
        retiring?.setEnabled(true)
        retiring = nil

        let replacement = InputRuntime()
        replacement.setEnabled(true)
        XCTAssertNotEqual(replacement.state, .active)
        replacement.setEnabled(false)
        XCTAssertEqual(replacement.state, .off)
    }
}
