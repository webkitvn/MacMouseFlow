import Bridge
import CoreGraphics
import Dispatch
import Foundation
@_spi(Benchmark) import Platform

let defaultCount = 100_000
let count = Int(ProcessInfo.processInfo.environment["MMF_BENCHMARK_EVENTS"] ?? "") ?? defaultCount
let eventCount = count > 0 ? count : defaultCount
let warmupCount = 1_000
let ciMode = ProcessInfo.processInfo.environment["MMF_BENCHMARK_CI"] == "1"
let syntheticMode = ProcessInfo.processInfo.environment["MMF_BENCHMARK_SYNTHETIC"] == "1"
let traceEnabled = ProcessInfo.processInfo.environment["MMF_TRACE"] != "0"

typealias WorkItem = (event: CGEvent, direction: ScrollDirection, amount: UInt32, expected: (horizontal: Int64, vertical: Int64)?)

func command(_ executable: String, _ arguments: String...) throws -> String {
    let task = Process()
    task.executableURL = URL(fileURLWithPath: executable)
    task.arguments = arguments
    let output = Pipe()
    task.standardOutput = output
    try task.run()
    task.waitUntilExit()
    guard task.terminationStatus == 0 else { throw NSError(domain: "benchmark", code: 1) }
    return String(decoding: output.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
}

func line(_ horizontal: Int32, _ vertical: Int32) -> CGEvent {
    CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: vertical, wheel2: horizontal, wheel3: 0)!
}

func pixel(_ horizontal: Int32, _ vertical: Int32) -> CGEvent {
    CGEvent(scrollWheelEvent2Source: nil, units: .pixel, wheelCount: 2, wheel1: vertical, wheel2: horizontal, wheel3: 0)!
}

if !ciMode && !syntheticMode {
    let hardware = try command("/usr/sbin/system_profiler", "SPHardwareDataType")
    let system = try command("/usr/bin/sw_vers")
    let power = try command("/usr/bin/pmset", "-g", "batt")
    let settings = try command("/usr/bin/pmset", "-g")
    guard hardware.contains("MacBookPro17,1"), hardware.contains("Apple M1"), hardware.contains("Memory: 16 GB"),
          system.contains("26.6.2"), system.contains("25G83"), power.contains("AC Power"), settings.contains("lowpowermode         0")
    else {
        fputs("reference Mac/power prerequisites not satisfied\n", stderr)
        exit(2)
    }
}

guard let engine = PointerInputEngine() else { exit(1) }
let callback = CallbackHarness(engine: engine, trace: traceEnabled)
let enabled: [WorkItem] = [
    (line(4, 0), .preserve, 25, (100, 0)),
    (line(0, 4), .preserve, 100, (0, 400)),
    (line(100, -100), .preserve, 137, (13_700, -13_700)),
    (line(-4, 4), .reverse, 400, (1_600, -1_600)),
    (line(4, 0), .reverse, 50, (-200, 0)),
    (line(0, -4), .preserve, 25, (0, -100)),
    (line(4, -2), .reverse, 137, (-548, 274)), // expected = (-5.48, +2.74), verified through fixed-point native fields.
    (line(0, 0), .preserve, 400, nil),
]
let pixelItem: WorkItem = (pixel(3, -2), .reverse, 400, nil)
let sequence = (0..<eventCount).map { index -> WorkItem in
    index.isMultiple(of: 10) ? pixelItem : enabled[index % enabled.count]
}

func matches(_ event: CGEvent, before: CFData?, expected: (horizontal: Int64, vertical: Int64)?) -> Bool {
    guard let expected else { return event.data == before }
    return abs(event.getDoubleValueField(.scrollWheelEventFixedPtDeltaAxis2) - Double(expected.horizontal) / 100) < 1 / 65_536
        && abs(event.getDoubleValueField(.scrollWheelEventFixedPtDeltaAxis1) - Double(expected.vertical) / 100) < 1 / 65_536
}

func verify(_ item: WorkItem, callback: CallbackHarness) -> Bool {
    guard callback.setConfiguration(item.direction, amountPercent: item.amount) else { return false }
    let event = item.event.copy()!
    let before = event.data
    callback.invoke(.scrollWheel, event: event)
    return matches(event, before: before, expected: item.expected)
}

for (index, item) in enabled.enumerated() {
    guard verify(item, callback: callback) else { fputs("benchmark workload expectation failed at item \(index)\n", stderr); exit(1) }
}
guard callback.setConfiguration(.reverse, amountPercent: 400) else { exit(1) }
let pixelBefore = pixelItem.event.data
callback.invoke(.scrollWheel, event: pixelItem.event)
guard pixelItem.event.data == pixelBefore else { fputs("pixel preservation failed\n", stderr); exit(1) }
for _ in 0..<warmupCount {
    guard verify(enabled[0], callback: callback) else { exit(1) }
}
var abiSamples = [UInt64](repeating: 0, count: eventCount)
var callbackSamples = [UInt64](repeating: 0, count: eventCount)
var amountUpdates = 0
for index in sequence.indices {
    let item = sequence[index]
    guard callback.setConfiguration(item.direction, amountPercent: item.amount) else { exit(1) }
    amountUpdates += 1
    let event = item.event.copy()!
    let before = event.data
    let abiStart = DispatchTime.now().uptimeNanoseconds
    _ = engine.evaluate(
        horizontal: event.getIntegerValueField(.scrollWheelEventDeltaAxis2),
        vertical: event.getIntegerValueField(.scrollWheelEventDeltaAxis1)
    )
    abiSamples[index] = DispatchTime.now().uptimeNanoseconds - abiStart
    let callbackStart = DispatchTime.now().uptimeNanoseconds
    callback.invoke(.scrollWheel, event: event)
    callbackSamples[index] = DispatchTime.now().uptimeNanoseconds - callbackStart
    guard matches(event, before: before, expected: item.expected) else { fputs("benchmark decision diverged\n", stderr); exit(1) }
}

guard amountUpdates >= 1_000 else { fputs("benchmark requires at least 1000 validated updates\n", stderr); exit(1) }

func metrics(_ samples: inout [UInt64]) -> (UInt64, UInt64, UInt64) {
    samples.sort()
    return (samples[Int(Double(eventCount - 1) * 0.99)], samples[Int(Double(eventCount - 1) * 0.999)], samples[eventCount - 1])
}
let abi = metrics(&abiSamples)
callback.close()
if traceEnabled {
    guard callback.cleanTraceShutdown() else { fputs("trace bundle failed clean shutdown\n", stderr); exit(1) }
    print("trace bundle clean: drop_count=0 writer_failed=false clean_shutdown=true")
}
let callbackMetrics = metrics(&callbackSamples)
print("workload events=\(eventCount) amount_updates=\(amountUpdates) amounts=25,100,137,400 directions=preserve,reverse axes=horizontal,vertical,multi,zero pixel_preserved")
print("ABI+Rust p99=\(abi.0)ns")
if ciMode {
    print("hosted regression production callback-body p99=\(callbackMetrics.0)ns p99.9=\(callbackMetrics.1)ns max=\(callbackMetrics.2)ns")
    guard abi.0 <= 500_000, callbackMetrics.0 <= 2_000_000 else { exit(1) }
    print("Hosted regression thresholds passed; non-reference evidence.")
} else if syntheticMode {
    print("synthetic production callback-body diagnostic p99=\(callbackMetrics.0)ns p99.9=\(callbackMetrics.1)ns max=\(callbackMetrics.2)ns")
    print("Diagnostic only; non-acceptance evidence.")
} else {
    print("production callback-body p99=\(callbackMetrics.0)ns p99.9=\(callbackMetrics.1)ns max=\(callbackMetrics.2)ns")
    guard abi.0 <= 100_000, callbackMetrics.0 <= 500_000, callbackMetrics.1 <= 1_000_000, callbackMetrics.2 <= 2_000_000 else { exit(1) }
}
