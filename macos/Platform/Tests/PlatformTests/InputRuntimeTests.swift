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

    func testLoadedAmountSurvivesRefreshAndExistingControls() throws {
        let store = ConfigurationStore(directory: directory)
        XCTAssertTrue(store.persist(.init(enabled: false, direction: .reverse, amountPercent: 137)))
        let runtime = InputRuntime(store: store)
        XCTAssertEqual(runtime.configuration.amountPercent, 137)
        runtime.refresh()
        runtime.setDirection(.preserve)
        runtime.setEnabled(false)
        XCTAssertEqual(runtime.configuration, .init(enabled: false, direction: .preserve, amountPercent: 137))
        XCTAssertEqual(store.load().0, runtime.configuration)
    }

    func testAmountTransactionsPreserveWholeConfigurationAcrossRestart() throws {
        let store = ConfigurationStore(directory: directory)
        XCTAssertTrue(store.persist(.init(enabled: false, direction: .reverse)))
        let runtime = InputRuntime(store: store)
        for amount: UInt32 in [25, 100, 137, 400] {
            runtime.setAmountPercent(amount)
            let expected = PersistedConfiguration(enabled: false, direction: .reverse, amountPercent: amount)
            XCTAssertEqual(runtime.configuration, expected)
            XCTAssertEqual(runtime.configurationAttention, .none)
            XCTAssertEqual(InputRuntime(store: store).configuration, expected)
            runtime.setDirection(.preserve)
            XCTAssertEqual(runtime.configuration, .init(enabled: false, direction: .preserve, amountPercent: amount))
            XCTAssertEqual(store.load().0, runtime.configuration)
            runtime.setDirection(.reverse)
        }
    }

    func testInvalidAmountTransactionKeepsCommittedFileAndSnapshot() throws {
        let store = ConfigurationStore(directory: directory)
        let committed = PersistedConfiguration(enabled: false, direction: .reverse, amountPercent: 137)
        XCTAssertTrue(store.persist(committed))
        let bytes = try Data(contentsOf: store.url)
        let runtime = InputRuntime(store: store)
        for amount: UInt32 in [0, 24, 401, .max] {
            runtime.setAmountPercent(amount)
            XCTAssertEqual(runtime.configuration, committed)
            XCTAssertEqual(runtime.configurationAttention, .saveFailed)
            XCTAssertEqual(try Data(contentsOf: store.url), bytes)
        }
        runtime.setAmountPercent(25)
        XCTAssertEqual(runtime.configuration.amountPercent, 25)
        XCTAssertEqual(runtime.configurationAttention, .none)
    }

    func testFailedAmountWriteKeepsFileAndSnapshotAndAllowsRetry() throws {
        let store = ConfigurationStore(directory: directory)
        let committed = PersistedConfiguration(enabled: false, direction: .reverse, amountPercent: 137)
        XCTAssertTrue(store.persist(committed))
        let bytes = try Data(contentsOf: store.url)
        let runtime = InputRuntime(store: store)
        try FileManager.default.setAttributes([.posixPermissions: 0o555], ofItemAtPath: directory.path)
        defer { try? FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: directory.path) }
        runtime.setAmountPercent(400)
        XCTAssertEqual(runtime.configuration, committed)
        XCTAssertEqual(runtime.configurationAttention, .saveFailed)
        XCTAssertEqual(try Data(contentsOf: store.url), bytes)
        XCTAssertTrue(runtime.canEditConfiguration)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: directory.path)
        runtime.setAmountPercent(400)
        XCTAssertEqual(runtime.configuration, .init(enabled: false, direction: .reverse, amountPercent: 400))
        XCTAssertEqual(store.load().0, runtime.configuration)
        XCTAssertEqual(runtime.configurationAttention, .none)
    }

    func testNewerSchemaAppearingAfterLoadBlocksAllTransactions() throws {
        let store = ConfigurationStore(directory: directory)
        let committed = PersistedConfiguration(enabled: false, direction: .reverse, amountPercent: 137)
        for version in ["3", "18446744073709551615"] {
            for operation in 0..<3 {
                try? FileManager.default.removeItem(at: store.url)
                XCTAssertTrue(store.persist(committed))
                let runtime = InputRuntime(store: store)
                let bytes = Data("{\"schema_version\":\(version),\"scroll\":\"future\"}".utf8)
                try bytes.write(to: store.url, options: .atomic)
                switch operation {
                case 0: runtime.setAmountPercent(400)
                case 1: runtime.setDirection(.preserve)
                default: runtime.setEnabled(true)
                }
                XCTAssertEqual(runtime.configuration, committed)
                XCTAssertEqual(runtime.configurationAttention, .newerSchema)
                XCTAssertEqual(runtime.state, .configurationNeedsAttention)
                XCTAssertFalse(runtime.canEditConfiguration)
                runtime.setAmountPercent(25)
                runtime.setDirection(.preserve)
                runtime.setEnabled(false)
                runtime.resetMalformedConfiguration()
                runtime.refresh()
                XCTAssertEqual(runtime.configuration, committed)
                XCTAssertEqual(try Data(contentsOf: store.url), bytes)
            }
        }
    }

    func testOversizedSchemaAppearingAfterLoadRefusesSaveAndReset() throws {
        let store = ConfigurationStore(directory: directory)
        let committed = PersistedConfiguration(enabled: false, direction: .reverse, amountPercent: 137)
        XCTAssertTrue(store.persist(committed))
        let runtime = InputRuntime(store: store)
        let bytes = Data(#"{"schema_version":18446744073709551616,"future":true}"#.utf8)
        try bytes.write(to: store.url)
        runtime.setAmountPercent(400)
        XCTAssertEqual(runtime.configuration, committed)
        XCTAssertEqual(runtime.configurationAttention, .newerSchema)
        XCTAssertFalse(runtime.canEditConfiguration)
        runtime.resetMalformedConfiguration()
        XCTAssertEqual(runtime.configuration, committed)
        XCTAssertEqual(try Data(contentsOf: store.url), bytes)
    }

    func testPreciseDecimalVersionAboveTwoRefusesSaveAndResetAfterLoad() throws {
        let store = ConfigurationStore(directory: directory)
        let committed = PersistedConfiguration(enabled: false, direction: .reverse, amountPercent: 137)
        for version in ["2.0000000000000000001", "2.0000000000000004", "1e200"] {
            try? FileManager.default.removeItem(at: store.url)
            XCTAssertTrue(store.persist(committed))
            let runtime = InputRuntime(store: store)
            let bytes = Data("{\"schema_version\":\(version),\"future\":true}".utf8)
            try bytes.write(to: store.url)
            runtime.setAmountPercent(400)
            XCTAssertEqual(runtime.configuration, committed)
            XCTAssertEqual(runtime.configurationAttention, .newerSchema)
            XCTAssertFalse(runtime.canEditConfiguration)
            runtime.resetMalformedConfiguration()
            XCTAssertEqual(runtime.configuration, committed)
            XCTAssertEqual(try Data(contentsOf: store.url), bytes)
        }
    }

    func testResetCannotOverwriteNewerSchemaAppearingAfterMalformedLoad() throws {
        let store = ConfigurationStore(directory: directory)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try Data("invalid".utf8).write(to: store.url)
        let runtime = InputRuntime(store: store)
        let bytes = Data(#"{"schema_version":3,"future":true}"#.utf8)
        try bytes.write(to: store.url)
        runtime.resetMalformedConfiguration()
        XCTAssertEqual(runtime.configuration, .default)
        XCTAssertEqual(runtime.configurationAttention, .newerSchema)
        XCTAssertFalse(runtime.canEditConfiguration)
        XCTAssertEqual(try Data(contentsOf: store.url), bytes)
    }

    func testMalformedReplacementBlocksNormalTransactionsButAllowsExplicitReset() throws {
        let store = ConfigurationStore(directory: directory)
        let committed = PersistedConfiguration(enabled: false, direction: .reverse, amountPercent: 137)
        for text in ["broken JSON", "{\"schema_version\":1" + String(repeating: "0", count: 166) + "}", #"{"schema_version":2}"#, #"{"schema_version":2,"scroll":{"enabled":1,"line_direction":"reverse","line_amount_percent":137}}"#, #"{"schema_version":2,"scroll":{"enabled":false,"line_direction":"reverse","line_amount_percent":401}}"#] {
            for operation in 0..<3 {
                try? FileManager.default.removeItem(at: store.url)
                XCTAssertTrue(store.persist(committed))
                let runtime = InputRuntime(store: store)
                let bytes = Data(text.utf8)
                try bytes.write(to: store.url)
                switch operation {
                case 0: runtime.setAmountPercent(400)
                case 1: runtime.setDirection(.preserve)
                default: runtime.setEnabled(true)
                }
                XCTAssertEqual(runtime.configuration, committed)
                XCTAssertEqual(runtime.configurationAttention, .malformed)
                XCTAssertFalse(runtime.canEditConfiguration)
                XCTAssertNotEqual(runtime.state, .active)
                XCTAssertEqual(try Data(contentsOf: store.url), bytes)
                runtime.resetMalformedConfiguration()
                XCTAssertEqual(runtime.configuration, .default)
                XCTAssertEqual(runtime.configurationAttention, .none)
                XCTAssertEqual(store.load().0, .default)
            }
        }
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
        XCTAssertTrue(runtime.canEditConfiguration)
        XCTAssertFalse(runtime.migrationFailed)

        try FileManager.default.removeItem(at: store.url)
        XCTAssertTrue(store.persist(committed))
        runtime.setDirection(.preserve)
        XCTAssertEqual(runtime.configuration, .init(enabled: true, direction: .preserve))
        XCTAssertEqual(runtime.configurationAttention, .none)
        XCTAssertEqual(store.load().0, runtime.configuration)
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
