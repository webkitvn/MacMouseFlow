import Bridge
import CoreGraphics
import Dispatch
import Platform

let count = 100_000
let engine = PointerInputEngine()!
precondition(engine.setReverseDirection())
let events = (0..<count).map { _ in
    CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 3, wheel2: -2, wheel3: 0)!
}
for event in events.prefix(1_000) { ScrollAdapter.process(event, engine: engine) }
var samples = [UInt64](repeating: 0, count: count)
for index in events.indices {
    let start = DispatchTime.now().uptimeNanoseconds
    ScrollAdapter.process(events[index], engine: engine)
    samples[index] = DispatchTime.now().uptimeNanoseconds - start
}
samples.sort()
let p99 = samples[Int((Double(count - 1) * 0.99).rounded(.up))]
let p999 = samples[Int((Double(count - 1) * 0.999).rounded(.up))]
let maximum = samples.last!
print("callback ns: p99=\(p99) p99.9=\(p999) max=\(maximum)")
guard p99 <= 500_000, p999 <= 1_000_000, maximum <= 2_000_000 else {
    fputs("callback latency threshold failed; this host is not reference-Mac evidence\n", stderr)
    exit(1)
}
