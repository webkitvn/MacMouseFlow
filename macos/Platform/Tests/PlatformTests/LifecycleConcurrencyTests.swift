@testable import Platform
import Bridge
import Foundation
import XCTest

private final class SharedRuntime: @unchecked Sendable {
    let value: ScrollRuntime
    init(_ value: ScrollRuntime) { self.value = value }
}

final class LifecycleConcurrencyTests: XCTestCase {
    func testRealRuntimeStartAndConcurrentStopJoinOnce() throws {
        let runtime = SharedRuntime(try XCTUnwrap(
            ScrollRuntime(testingWithoutTap: try XCTUnwrap(PointerInputEngine()))
        ))
        XCTAssertTrue(runtime.value.start())
        DispatchQueue.concurrentPerform(iterations: 32) { _ in runtime.value.stop() }
    }
}
