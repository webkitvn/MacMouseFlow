import Bridge
import CoreGraphics
import Platform
import XCTest

final class ScrollRuntimeTests: XCTestCase {
    func testUnavailablePermissionHasNoRuntimeToStop() {
        if let runtime = ScrollRuntime() {
            XCTAssertTrue(runtime.stop())
            XCTAssertTrue(runtime.stop())
        }
    }

    func testLineBasedAxesReverseThroughABI() throws {
        let engine = try XCTUnwrap(PointerInputEngine())
        XCTAssertTrue(engine.setReverseDirection())
        let event = try XCTUnwrap(CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 3, wheel2: -2, wheel3: 0))
        ScrollAdapter.process(event, engine: engine)
        XCTAssertEqual(event.getIntegerValueField(.scrollWheelEventDeltaAxis1), -3)
        XCTAssertEqual(event.getIntegerValueField(.scrollWheelEventDeltaAxis2), 2)
    }

    func testSystemDirectionPreservesLineEvent() throws {
        let engine = try XCTUnwrap(PointerInputEngine())
        XCTAssertTrue(engine.setSystemDirection())
        let event = try XCTUnwrap(CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 3, wheel2: -2, wheel3: 0))
        ScrollAdapter.process(event, engine: engine)
        XCTAssertEqual(event.getIntegerValueField(.scrollWheelEventDeltaAxis1), 3)
        XCTAssertEqual(event.getIntegerValueField(.scrollWheelEventDeltaAxis2), -2)
    }

    func testPixelBasedAndUnexpectedEventsArePreserved() throws {
        let engine = try XCTUnwrap(PointerInputEngine())
        XCTAssertTrue(engine.setReverseDirection())
        let pixel = try XCTUnwrap(CGEvent(scrollWheelEvent2Source: nil, units: .pixel, wheelCount: 2, wheel1: 3, wheel2: -2, wheel3: 0))
        let pixelAxis1 = pixel.getIntegerValueField(.scrollWheelEventDeltaAxis1)
        let pixelAxis2 = pixel.getIntegerValueField(.scrollWheelEventDeltaAxis2)
        ScrollAdapter.process(pixel, engine: engine)
        XCTAssertEqual(pixel.getIntegerValueField(.scrollWheelEventDeltaAxis1), pixelAxis1)
        XCTAssertEqual(pixel.getIntegerValueField(.scrollWheelEventDeltaAxis2), pixelAxis2)

        let mouse = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: .zero, mouseButton: .left)!
        let flags = mouse.flags
        ScrollAdapter.process(mouse, engine: engine)
        XCTAssertEqual(mouse.flags, flags)
    }

    func testPhaseAndMomentumDoNotAffectLineEligibility() throws {
        let engine = try XCTUnwrap(PointerInputEngine())
        XCTAssertTrue(engine.setReverseDirection())
        let event = try XCTUnwrap(CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 3, wheel2: -2, wheel3: 0))
        event.setIntegerValueField(.scrollWheelEventScrollPhase, value: 9)
        event.setIntegerValueField(.scrollWheelEventMomentumPhase, value: 7)
        ScrollAdapter.process(event, engine: engine)
        XCTAssertEqual(event.getIntegerValueField(.scrollWheelEventDeltaAxis1), -3)
        XCTAssertEqual(event.getIntegerValueField(.scrollWheelEventDeltaAxis2), 2)
    }
}
