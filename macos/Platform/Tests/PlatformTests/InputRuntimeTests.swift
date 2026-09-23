import Foundation
import Platform
import XCTest

final class InputRuntimeTests: XCTestCase {
    private var directory: URL!

    override func setUpWithError() throws {
        directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: directory)
    }

    private func runtime() -> InputRuntime {
        InputRuntime(store: ConfigurationStore(directory: directory))
    }

    func testStateResolutionContract() {
        XCTAssertEqual(InputRuntimeState.resolve(enabled: false, accessibilityTrusted: true, runtimeStatus: .active, attention: .none), .off)
        XCTAssertEqual(InputRuntimeState.resolve(enabled: false, accessibilityTrusted: false, runtimeStatus: .unavailable, attention: .none), .off)
        XCTAssertEqual(InputRuntimeState.resolve(enabled: true, accessibilityTrusted: false, runtimeStatus: .active, attention: .none), .needsAccessibilityAccess)
        XCTAssertEqual(InputRuntimeState.resolve(enabled: true, accessibilityTrusted: false, runtimeStatus: .unavailable, attention: .none), .needsAccessibilityAccess)
        XCTAssertEqual(InputRuntimeState.resolve(enabled: true, accessibilityTrusted: true, runtimeStatus: .active, attention: .none), .active)
        XCTAssertEqual(InputRuntimeState.resolve(enabled: true, accessibilityTrusted: true, runtimeStatus: .unavailable, attention: .none), .inputUnavailable)
    }

    func testEnablingPublishesTruthfulNonActiveStateSynchronously() {
        let runtime = runtime()
        runtime.setEnabled(true)
        XCTAssertNotEqual(runtime.state, .active)
        XCTAssertNotEqual(runtime.state, .off)
        runtime.setEnabled(false)
    }

    func testDisablePublishesOffWithoutApprovalFromLifecycleExecutor() {
        let runtime = runtime()
        runtime.setEnabled(true)
        runtime.setEnabled(false)
        XCTAssertEqual(runtime.state, .off)

        runtime.refresh()
        XCTAssertEqual(runtime.state, .off)
    }

    func testFailedSaveKeepsCommittedEnabledDirectionThroughRefresh() throws {
        let store = ConfigurationStore(directory: directory)
        let committed = PersistedConfiguration(enabled: true, direction: .reverse)
        XCTAssertTrue(store.persist(committed))
        let runtime = InputRuntime(store: store)
        try FileManager.default.removeItem(at: store.url)
        try FileManager.default.createDirectory(at: store.url, withIntermediateDirectories: true)

        runtime.setDirection(.preserve)
        runtime.refresh()

        XCTAssertEqual(runtime.configuration, committed)
        XCTAssertEqual(runtime.configurationAttention, .saveFailed)
        XCTAssertNotEqual(runtime.state, .off)
        XCTAssertNotEqual(runtime.state, .configurationNeedsAttention)
    }

    func testReleasingRuntimeDoesNotBlockOrPoisonSubsequentRuntimes() {
        var retiring: InputRuntime? = runtime()
        retiring?.setEnabled(true)
        retiring = nil

        let replacement = runtime()
        replacement.setEnabled(true)
        XCTAssertNotEqual(replacement.state, .active)
        replacement.setEnabled(false)
        XCTAssertEqual(replacement.state, .off)
    }
}
