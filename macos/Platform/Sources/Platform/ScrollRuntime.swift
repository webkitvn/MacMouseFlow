import AppKit
import Bridge
import CoreGraphics

public enum ScrollAdapter {
    public static func process(_ event: CGEvent, engine: PointerInputEngine) {
        guard event.type == .scrollWheel,
              event.getIntegerValueField(.scrollWheelEventIsContinuous) == 0,
              let decision = engine.evaluate(
                horizontal: event.getIntegerValueField(.scrollWheelEventDeltaAxis2),
                vertical: event.getIntegerValueField(.scrollWheelEventDeltaAxis1)
              )
        else { return }
        guard case let .replace(horizontal, vertical) = decision else { return }
        event.setIntegerValueField(.scrollWheelEventDeltaAxis1, value: vertical)
        event.setIntegerValueField(.scrollWheelEventDeltaAxis2, value: horizontal)
    }
}

public final class ScrollRuntime {
    private let engine: PointerInputEngine
    private var tap: CFMachPort?
    private var source: CFRunLoopSource?
    private var runLoop: CFRunLoop?
    private var timeoutCount = 0

    public init?() {
        // Event delivery, start, stop, and destruction are confined to the main run loop.
        precondition(Thread.isMainThread)
        guard AXIsProcessTrusted(), let engine = PointerInputEngine() else { return nil }
        self.engine = engine
    }

    public func start() -> Bool {
        precondition(Thread.isMainThread)
        guard tap == nil else { return false }
        let mask = CGEventMask(1) << CGEventType.scrollWheel.rawValue
        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: mask,
            callback: Self.callback,
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        ) else { return false }
        let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        let runLoop = CFRunLoopGetMain()
        self.tap = tap
        self.source = source
        self.runLoop = runLoop
        CFRunLoopAddSource(runLoop, source, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)
        guard CGEvent.tapIsEnabled(tap: tap) else {
            stop()
            return false
        }
        return true
    }

    public func stop() {
        precondition(Thread.isMainThread)
        guard let tap else { return }
        CGEvent.tapEnable(tap: tap, enable: false)
        if let source, let runLoop { CFRunLoopRemoveSource(runLoop, source, .commonModes) }
        source = nil
        runLoop = nil
        self.tap = nil
    }

    public var disabledByTimeoutCount: Int {
        precondition(Thread.isMainThread)
        return timeoutCount
    }

    deinit {
        precondition(Thread.isMainThread)
        stop()
    }

    private static let callback: CGEventTapCallBack = { _, type, event, info in
        guard let info else { return Unmanaged.passUnretained(event) }
        let runtime = Unmanaged<ScrollRuntime>.fromOpaque(info).takeUnretainedValue()
        if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
            if type == .tapDisabledByTimeout { runtime.timeoutCount += 1 }
            if let tap = runtime.tap { CGEvent.tapEnable(tap: tap, enable: true) }
        } else {
            ScrollAdapter.process(event, engine: runtime.engine)
        }
        return Unmanaged.passUnretained(event)
    }
}
