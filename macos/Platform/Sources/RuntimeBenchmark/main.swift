import Bridge
import CoreGraphics
import Dispatch
import Foundation
@_spi(Benchmark) import Platform

let count = 100_000
let engine = PointerInputEngine()!
precondition(engine.setReverseDirection())
let callback = CallbackHarness(engine: engine)
let trace = (0..<count).map { index -> (CGEventType, CGEvent) in
    let units: CGScrollEventUnit = index.isMultiple(of: 4) ? .pixel : .line
    return (.scrollWheel, CGEvent(scrollWheelEvent2Source: nil, units: units, wheelCount: 2, wheel1: 3, wheel2: -2, wheel3: 0)!)
}
for (type, event) in trace.prefix(1_000) { callback.invoke(type, event: event) }
var ffiSamples = [UInt64](repeating: 0, count: count)
var callbackSamples = [UInt64](repeating: 0, count: count)
for index in trace.indices {
    if index.isMultiple(of: 100) { precondition(engine.setSystemDirection()) }
    if index % 100 == 50 { precondition(engine.setReverseDirection()) }
    let type = trace[index].0
    let event = trace[index].1
    let horizontal = event.getIntegerValueField(.scrollWheelEventDeltaAxis2)
    let vertical = event.getIntegerValueField(.scrollWheelEventDeltaAxis1)
    let ffiStart = DispatchTime.now().uptimeNanoseconds
    _ = engine.evaluate(horizontal: horizontal, vertical: vertical)
    ffiSamples[index] = DispatchTime.now().uptimeNanoseconds - ffiStart
    let callbackStart = DispatchTime.now().uptimeNanoseconds
    callback.invoke(type, event: event)
    callbackSamples[index] = DispatchTime.now().uptimeNanoseconds - callbackStart
}

func report(_ name: String, samples: inout [UInt64]) -> (UInt64, UInt64, UInt64) {
    samples.sort()
    let p99 = samples[Int((Double(count - 1) * 0.99).rounded(.up))]
    let p999 = samples[Int((Double(count - 1) * 0.999).rounded(.up))]
    let maximum = samples.last!
    print("\(name) ns: p99=\(p99) p99.9=\(p999) max=\(maximum)")
    return (p99, p999, maximum)
}

let ffi = report("abi+rustr", samples: &ffiSamples)
let adapter = report("synthetic adapter", samples: &callbackSamples)
let ciMode = ProcessInfo.processInfo.environment["MMF_BENCHMARK_CI"] == "1"
if ciMode {
    precondition(ffi.0 <= 500_000)
    precondition(adapter.0 <= 2_000_000)
    print("Hosted regression thresholds passed; not reference-Mac callback/re-enable evidence.")
} else {
    print("Synthetic diagnostic only: it does not install a tap or measure lifecycle re-enable.")
}
