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
print("macOS LineBased reversal passed")
