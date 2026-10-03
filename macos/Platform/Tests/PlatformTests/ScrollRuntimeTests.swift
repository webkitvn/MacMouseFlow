import AppKit
import Bridge
import CoreGraphics
@_spi(Benchmark) import Platform
import XCTest

final class ScrollRuntimeTests: XCTestCase {
    func testExactAmountThroughBridgeAndNativeFields() throws {
        let engine = try XCTUnwrap(PointerInputEngine())
        for (direction, amount, expected) in [(ScrollDirection.preserve, UInt32(25), Int64(25)), (.preserve, 50, 50), (.preserve, 137, 137), (.reverse, 100, -100), (.reverse, 50, -50)] {
            XCTAssertTrue(engine.setDirection(direction, amountPercent: amount))
            guard case let .replace(horizontal, vertical)? = engine.evaluate(horizontal: 1, vertical: -1) else { return XCTFail("expected exact replacement") }
            XCTAssertEqual(horizontal, expected)
            XCTAssertEqual(vertical, -expected)
            let event = try XCTUnwrap(CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: -1, wheel2: 1, wheel3: 0))
            let pointX = event.getIntegerValueField(.scrollWheelEventPointDeltaAxis2)
            let pointY = event.getIntegerValueField(.scrollWheelEventPointDeltaAxis1)
            XCTAssertEqual(ScrollAdapter.process(event, engine: engine), 1)
            let native = try XCTUnwrap(NSEvent(cgEvent: event))
            XCTAssertEqual(Double(native.scrollingDeltaX), Double(expected) / 100, accuracy: 1 / 65536)
            XCTAssertEqual(Double(native.scrollingDeltaY), Double(-expected) / 100, accuracy: 1 / 65536)
            XCTAssertEqual(event.getIntegerValueField(.scrollWheelEventIsContinuous), 0)
            if expected % 100 != 0 {
                XCTAssertEqual(event.getIntegerValueField(.scrollWheelEventPointDeltaAxis2), pointX)
                XCTAssertEqual(event.getIntegerValueField(.scrollWheelEventPointDeltaAxis1), pointY)
            }
        }
        XCTAssertFalse(engine.setDirection(.preserve, amountPercent: 24))
        XCTAssertFalse(engine.setDirection(.preserve, amountPercent: 401))
        guard case let .replace(horizontal, _)? = engine.evaluate(horizontal: 1, vertical: 0) else { return XCTFail("invalid config mutated state") }
        XCTAssertEqual(horizontal, -50)
    }

    func testMixedAxesAndFractionalRangePreflight() throws {
        for value: Int64 in [-3_276_799, 3_276_799, 137] {
            let event = try XCTUnwrap(CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 1, wheel2: 1, wheel3: 0))
            XCTAssertEqual(ScrollAdapter.apply(event, decision: .replace(horizontalHundredths: 200, verticalHundredths: value)), 1)
            XCTAssertEqual(event.getIntegerValueField(.scrollWheelEventDeltaAxis2), 2)
            XCTAssertEqual(event.getDoubleValueField(.scrollWheelEventFixedPtDeltaAxis1), Double(value) / 100, accuracy: 1 / 65536)
        }
        for (horizontal, vertical): (Int64, Int64) in [(200, 3_276_801), (-3_276_801, 200), (137, Int64.max), (Int64.min, 137)] {
            let event = try XCTUnwrap(CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 1, wheel2: -1, wheel3: 0))
            let before = event.data
            XCTAssertEqual(ScrollAdapter.apply(event, decision: .replace(horizontalHundredths: horizontal, verticalHundredths: vertical)), 2)
            XCTAssertEqual(event.data, before)
        }
        for lines: Int64 in [-32_768, 32_767] {
            let boundary = try XCTUnwrap(CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 1, wheel2: 1, wheel3: 0))
            XCTAssertEqual(ScrollAdapter.apply(boundary, decision: .replace(horizontalHundredths: lines * 100, verticalHundredths: lines * 100)), 1)
            XCTAssertEqual(boundary.getIntegerValueField(.scrollWheelEventDeltaAxis2), lines)
            XCTAssertEqual(boundary.getIntegerValueField(.scrollWheelEventDeltaAxis1), lines)
            let native = try XCTUnwrap(NSEvent(cgEvent: boundary))
            XCTAssertEqual(Double(native.scrollingDeltaX), Double(lines))
            XCTAssertEqual(Double(native.scrollingDeltaY), Double(lines))
        }
        for invalid: Int64 in [-3_276_900, 3_276_800] {
            for valid: Int64 in [200, 137] {
                for (horizontal, vertical) in [(invalid, valid), (valid, invalid)] {
                    let event = try XCTUnwrap(CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 1, wheel2: -1, wheel3: 0))
                    let before = event.data
                    XCTAssertEqual(ScrollAdapter.apply(event, decision: .replace(horizontalHundredths: horizontal, verticalHundredths: vertical)), 2)
                    XCTAssertEqual(event.data, before)
                }
            }
        }
    }

    func testProcessAndCallbackPreserveRejectedReplacementAndTraceRealOutcome() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let oldTrace = getenv("MMF_TRACE").map { String(cString: $0) }
        let oldDirectory = getenv("MMF_TRACE_DIR").map { String(cString: $0) }
        setenv("MMF_TRACE", "1", 1)
        setenv("MMF_TRACE_DIR", directory.path, 1)
        defer {
            if let oldTrace { setenv("MMF_TRACE", oldTrace, 1) } else { unsetenv("MMF_TRACE") }
            if let oldDirectory { setenv("MMF_TRACE_DIR", oldDirectory, 1) } else { unsetenv("MMF_TRACE_DIR") }
            try? FileManager.default.removeItem(at: directory)
        }
        let engine = try XCTUnwrap(PointerInputEngine())
        XCTAssertTrue(engine.setDirection(.preserve, amountPercent: 137))
        let callback = CallbackHarness(engine: engine)
        for wheel: Int32 in [1, 23_919] {
            let event = try XCTUnwrap(CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: wheel, wheel2: 100, wheel3: 0))
            let before = event.data
            let copy = try XCTUnwrap(event.copy())
            XCTAssertEqual(ScrollAdapter.process(copy, engine: engine), wheel == 1 ? 1 : 2)
            callback.invoke(.scrollWheel, event: event)
            if wheel != 1 { XCTAssertEqual(event.data, before); XCTAssertEqual(copy.data, before) }
        }
        callback.close()
        let run = try XCTUnwrap(FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil).first)
        let files = try FileManager.default.contentsOfDirectory(at: run, includingPropertiesForKeys: nil).filter { $0.pathExtension == "jsonl" }
        let records = try files.flatMap { try String(contentsOf: $0, encoding: .utf8).split(separator: "\n").map { try JSONSerialization.jsonObject(with: Data($0.utf8)) as! [String: Any] } }.filter { $0["name"] as? String == "input.pipeline" }.sorted { ($0["input_seq"] as! Int) < ($1["input_seq"] as! Int) }
        XCTAssertEqual(records.count, 2)
        XCTAssertEqual(records[0]["native_outcome"] as? String, "applied")
        XCTAssertEqual(records[1]["decision"] as? String, "replace")
        XCTAssertEqual(records[1]["native_outcome"] as? String, "preserved")
        XCTAssertEqual(records[1]["reason_code"] as? String, "preserve")
        XCTAssertTrue(records[1]["config_revision"] is NSNull)
        var repository = URL(fileURLWithPath: #filePath)
        for _ in 0..<5 { repository.deleteLastPathComponent() }
        let export = Process()
        export.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        export.arguments = ["python3", repository.appendingPathComponent("scripts/trace.py").path, "export", run.lastPathComponent, directory.appendingPathComponent("exported").path]
        export.environment = ProcessInfo.processInfo.environment
        let errors = Pipe()
        export.standardError = errors
        export.standardOutput = FileHandle.nullDevice
        try export.run()
        export.waitUntilExit()
        XCTAssertEqual(export.terminationStatus, 0, String(decoding: errors.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self))
        XCTAssertTrue(FileManager.default.fileExists(atPath: directory.appendingPathComponent("exported/manifest.json").path))
    }

    func testConcurrentEngineCreationRetriesBusy() {
        let workers = 8
        let ready = DispatchGroup()
        let finished = DispatchGroup()
        let start = DispatchSemaphore(value: 0)
        let lock = NSLock()
        var engines: [PointerInputEngine] = []

        for _ in 0..<workers {
            ready.enter()
            finished.enter()
            Thread {
                ready.leave()
                start.wait()
                if let engine = PointerInputEngine() {
                    lock.lock()
                    engines.append(engine)
                    lock.unlock()
                }
                finished.leave()
            }.start()
        }
        ready.wait()
        for _ in 0..<workers { start.signal() }
        finished.wait()
        XCTAssertEqual(engines.count, workers)
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
