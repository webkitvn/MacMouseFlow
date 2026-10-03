import AppKit
import Bridge
import CoreGraphics
import Platform

let engine = PointerInputEngine()!
precondition(engine.setReverseDirection())
let event = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 3, wheel2: -2, wheel3: 0)!
ScrollAdapter.process(event, engine: engine)
let result = NSEvent(cgEvent: event)!
precondition(result.scrollingDeltaX == 2 && result.scrollingDeltaY == -3)
precondition(engine.setDirection(.preserve, amountPercent: 137))
let fractional = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: -1, wheel2: 1, wheel3: 0)!
precondition(ScrollAdapter.process(fractional, engine: engine) == 1)
let fractionalResult = NSEvent(cgEvent: fractional)!
precondition(abs(Double(fractionalResult.scrollingDeltaX) - 1.37) <= 1 / 65536)
precondition(abs(Double(fractionalResult.scrollingDeltaY) + 1.37) <= 1 / 65536)
precondition(!fractionalResult.hasPreciseScrollingDeltas)
let invalid = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 2, wheel1: 23_919, wheel2: 100, wheel3: 0)!
let original = invalid.data
precondition(ScrollAdapter.process(invalid, engine: engine) == 2 && invalid.data == original)
print("macOS LineBased reversal, fractional amount, and atomic fail-open passed")
