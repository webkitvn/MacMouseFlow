import Bridge
import CoreGraphics
import Dispatch
import Foundation
@_spi(Benchmark) import Platform

let count = 100_000
let warmupCount = 1_000
let ciMode = ProcessInfo.processInfo.environment["MMF_BENCHMARK_CI"] == "1"
let syntheticMode = ProcessInfo.processInfo.environment["MMF_BENCHMARK_SYNTHETIC"] == "1"

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
let callback = CallbackHarness(engine: engine)
guard callback.setReverse(false) else { exit(1) }
let line = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 3, wheel2: -2, wheel3: 0)!
let pixel = CGEvent(scrollWheelEvent2Source: nil, units: .pixel, wheelCount: 2, wheel1: 3, wheel2: -2, wheel3: 0)!
let trace = (0..<count).map { index in index.isMultiple(of: 4) ? pixel.copy()! : line.copy()! }
let warmup = (0..<warmupCount).map { _ in line.copy()! }

for event in warmup { callback.invoke(.scrollWheel, event: event) }
var abiSamples = [UInt64](repeating: 0, count: count)
var callbackSamples = [UInt64](repeating: 0, count: count)
for index in trace.indices {
    if index.isMultiple(of: 100) {
        guard callback.setReverse((index / 100).isMultiple(of: 2)) else { exit(1) }
    }
    let event = trace[index]
    let abiStart = DispatchTime.now().uptimeNanoseconds
    _ = engine.evaluate(
        horizontal: event.getIntegerValueField(.scrollWheelEventDeltaAxis2),
        vertical: event.getIntegerValueField(.scrollWheelEventDeltaAxis1)
    )
    abiSamples[index] = DispatchTime.now().uptimeNanoseconds - abiStart
    let callbackStart = DispatchTime.now().uptimeNanoseconds
    callback.invoke(.scrollWheel, event: event)
    callbackSamples[index] = DispatchTime.now().uptimeNanoseconds - callbackStart
}

func metrics(_ samples: inout [UInt64]) -> (UInt64, UInt64, UInt64) {
    samples.sort()
    return (samples[Int(Double(count - 1) * 0.99)], samples[Int(Double(count - 1) * 0.999)], samples[count - 1])
}
let abi = metrics(&abiSamples)
let callbackMetrics = metrics(&callbackSamples)
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
