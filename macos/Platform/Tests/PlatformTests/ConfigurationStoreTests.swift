import Bridge
import Foundation
import Platform
import XCTest

final class ConfigurationStoreTests: XCTestCase {
    private var directory: URL!

    override func setUpWithError() throws {
        directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: directory)
    }

    func testFreshConfigurationDefaultsWithoutCreatingFile() {
        let store = ConfigurationStore(directory: directory)
        XCTAssertEqual(store.load().0, .default)
        XCTAssertEqual(store.load().1, .none)
        XCTAssertFalse(FileManager.default.fileExists(atPath: store.url.path))
    }

    func testV1ConfigurationPersistsAcrossRestart() {
        let store = ConfigurationStore(directory: directory)
        let expected = PersistedConfiguration(enabled: true, direction: .reverse)
        XCTAssertTrue(store.persist(expected))
        XCTAssertEqual(ConfigurationStore(directory: directory).load().0, expected)
    }

    func testMalformedConfigurationDefaultsWithoutRewrite() throws {
        let store = ConfigurationStore(directory: directory)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let data = Data("not json".utf8)
        try data.write(to: store.url)
        XCTAssertEqual(store.load().0, .default)
        XCTAssertEqual(store.load().1, .malformed)
        XCTAssertEqual(try Data(contentsOf: store.url), data)
    }

    func testFractionalOrSurplusV1DocumentDefaultsWithoutRewrite() throws {
        let store = ConfigurationStore(directory: directory)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        for text in [
            #"{"schema_version":1.0,"scroll":{"enabled":true,"line_direction":"reverse"}}"#,
            #"{"schema_version":1,"scroll":{"enabled":true,"line_direction":"reverse"},"extra":true}"#,
            #"{"schema_version":1,"scroll":{"enabled":true,"line_direction":"reverse","extra":true}}"#,
        ] {
            let data = Data(text.utf8)
            try data.write(to: store.url)
            XCTAssertEqual(store.load().0, .default)
            XCTAssertEqual(store.load().1, .malformed)
            XCTAssertEqual(try Data(contentsOf: store.url), data)
        }
    }

    func testNewerConfigurationIsReadOnlyWithoutRewrite() throws {
        let store = ConfigurationStore(directory: directory)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let data = Data(#"{"schema_version":2,"scroll":"not-v1"}"#.utf8)
        try data.write(to: store.url)
        XCTAssertEqual(store.load().0, .default)
        XCTAssertEqual(store.load().1, .newerSchema)
        XCTAssertEqual(try Data(contentsOf: store.url), data)
    }

    func testPersistFailureLeavesExistingConfigurationUnchanged() throws {
        let store = ConfigurationStore(directory: directory)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try Data().write(to: store.url)
        try FileManager.default.removeItem(at: store.url)
        try FileManager.default.createDirectory(at: store.url, withIntermediateDirectories: true)
        XCTAssertFalse(store.persist(.init(enabled: true, direction: .reverse)))
    }

    func testBridgeValidationAcceptsBothDirections() {
        XCTAssertTrue(validate(direction: .preserve))
        XCTAssertTrue(validate(direction: .reverse))
    }
}
