import Bridge
import CoreGraphics
import Dispatch
import Platform

let count = 100_000
let engine = PointerInputEngine()!
precondition(engine.setReverseDirection())
let trace = (0..<count).map { index -> (CGEventType, CGEvent) in
    let units: CGScrollEventUnit = index.isMultiple(of: 4) ? .pixel : .line
    return (.scrollWheel, CGEvent(scrollWheelEvent2Source: nil, units: units, wheelCount: 2, wheel1: 3, wheel2: -2, wheel3: 0)!)
}

for (type, event) in trace.prefix(1_000) { ScrollRuntime.dispatch(type, event: event, engine: engine) }
var ffiSamples = [UInt64](repeating: 0, count: count)
var callbackSamples = [UInt64](repeating: 0, count: count)
for index in trace.indices {
    if index.isMultiple(of: 100) { precondition(engine.setSystemDirection()) }
    if index % 100 == 50 { precondition(engine.setReverseDirection()) }
    if index.isMultiple(of: 1_000) {
        ScrollRuntime.dispatch(.tapDisabledByUserInput, event: trace[index].1, engine: engine)
    }

    let horizontal = trace[index].1.getIntegerValueField(.scrollWheelEventDeltaAxis2)
    let vertical = trace[index].1.getIntegerValueField(.scrollWheelEventDeltaAxis1)
    let ffiStart = DispatchTime.now().uptimeNanoseconds
    _ = engine.evaluate(horizontal: horizontal, vertical: vertical)
    ffiSamples[index] = DispatchTime.now().uptimeNanoseconds - ffiStart

    let callbackStart = DispatchTime.now().uptimeNanoseconds
    ScrollRuntime.dispatch(trace[index].0, event: trace[index].1, engine: engine)
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
let callback = report("callback", samples: &callbackSamples)
guard ffi.0 <= 100_000,
      callback.0 <= 500_000,
      callback.1 <= 1_000_000,
      callback.2 <= 2_000_000
else {
    fputs("benchmark threshold failed; this host is not reference-Mac evidence\n", stderr)
    exit(1)
}
