import AppKit
import Bridge
import CoreGraphics
import Foundation

public enum ScrollAdapter {
    public static func process(_ event: CGEvent, engine: PointerInputEngine) {
        guard event.type == .scrollWheel,
              event.getIntegerValueField(.scrollWheelEventIsContinuous) == 0,
              let decision = engine.evaluate(
                horizontal: event.getIntegerValueField(.scrollWheelEventDeltaAxis2),
                vertical: event.getIntegerValueField(.scrollWheelEventDeltaAxis1)
              ),
              case let .replace(horizontal, vertical) = decision
        else { return }
        event.setIntegerValueField(.scrollWheelEventDeltaAxis1, value: vertical)
        event.setIntegerValueField(.scrollWheelEventDeltaAxis2, value: horizontal)
    }
}

private final class TapState: @unchecked Sendable {
    // The lock publishes lifecycle state only. The callback never takes it.
    private let lock = NSLock()
    let engine: PointerInputEngine
    let ready = DispatchSemaphore(value: 0)
    let stopped = DispatchSemaphore(value: 0)
    private var threadStarted = false
    private var cancelled = false
    private var completed = false
    private var runLoop: CFRunLoop?
    private var timeoutCount = 0
    private var tap: CFMachPort?
    private var source: CFRunLoopSource?

    init(engine: PointerInputEngine) { self.engine = engine }

    func markThreadStarted() {
        lock.lock()
        threadStarted = true
        lock.unlock()
    }

    func run() {
        let runLoop = CFRunLoopGetCurrent()
        let mask = CGEventMask(1) << CGEventType.scrollWheel.rawValue
        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: mask,
            callback: ScrollRuntime.callback,
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        ) else {
            ready.signal()
            complete()
            return
        }
        let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        self.tap = tap
        self.source = source
        CFRunLoopAddSource(runLoop, source, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)

        lock.lock()
        let shouldRun = !cancelled && CGEvent.tapIsEnabled(tap: tap)
        self.runLoop = shouldRun ? runLoop : nil
        lock.unlock()
        ready.signal()
        guard shouldRun else {
            finishOnOwnerRunLoop()
            complete()
            return
        }
        CFRunLoopRun()
        finishOnOwnerRunLoop()
        complete()
    }

    func cancelAndRunLoop() -> (join: Bool, runLoop: CFRunLoop?) {
        lock.lock()
        defer { lock.unlock() }
        guard threadStarted, !completed else { return (false, nil) }
        cancelled = true
        return (true, runLoop)
    }

    func startSucceeded() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return runLoop != nil && !completed
    }

    func completedTimeoutCount() -> Int {
        lock.lock()
        defer { lock.unlock() }
        precondition(completed)
        return timeoutCount
    }

    func finishOnOwnerRunLoop() {
        if let tap { CGEvent.tapEnable(tap: tap, enable: false) }
        if let source { CFRunLoopRemoveSource(CFRunLoopGetCurrent(), source, .commonModes) }
        tap = nil
        source = nil
        lock.lock()
        runLoop = nil
        lock.unlock()
    }

    func disabledByTimeout() { timeoutCount += 1 }
    func reenable() { if let tap { CGEvent.tapEnable(tap: tap, enable: true) } }

    private func complete() {
        lock.lock()
        guard !completed else {
            lock.unlock()
            return
        }
        completed = true
        runLoop = nil
        lock.unlock()
        stopped.signal()
    }
}

public final class ScrollRuntime {
    private let state: TapState
    private let thread: Thread
    private var stopJoined = false

    public init?(reverseForHarness: Bool = false) {
        guard AXIsProcessTrusted(), let engine = PointerInputEngine() else { return nil }
        guard reverseForHarness ? engine.setReverseDirection() : engine.setSystemDirection() else { return nil }
        let state = TapState(engine: engine)
        self.state = state
        thread = Thread { state.run() }
        thread.name = "MacMouseFlow CGEventTap"
    }

    public func start() -> Bool {
        guard !thread.isExecuting, !stopJoined else { return false }
        state.markThreadStarted()
        thread.start()
        guard state.ready.wait(timeout: .now() + 1) == .success else {
            _ = stop()
            return false
        }
        return state.startSucceeded()
    }

    @discardableResult
    public func stop() -> Bool {
        guard !stopJoined else { return true }
        let request = state.cancelAndRunLoop()
        guard request.join else {
            stopJoined = true
            return true
        }
        if let runLoop = request.runLoop {
            CFRunLoopPerformBlock(runLoop, CFRunLoopMode.defaultMode.rawValue as NSString) {
                self.state.finishOnOwnerRunLoop()
                CFRunLoopStop(runLoop)
            }
            CFRunLoopWakeUp(runLoop)
        }
        // This is outside the callback; destruction cannot proceed while the owner thread runs.
        _ = state.stopped.wait(timeout: .distantFuture)
        stopJoined = true
        return true
    }

    public var disabledByTimeoutCount: Int {
        precondition(stopJoined)
        return state.completedTimeoutCount()
    }

    deinit { _ = stop() }

    public static func dispatch(_ type: CGEventType, event: CGEvent, engine: PointerInputEngine) {
        guard type != .tapDisabledByTimeout, type != .tapDisabledByUserInput else { return }
        ScrollAdapter.process(event, engine: engine)
    }

    fileprivate static let callback: CGEventTapCallBack = { _, type, event, info in
        guard let info else { return Unmanaged.passUnretained(event) }
        let state = Unmanaged<TapState>.fromOpaque(info).takeUnretainedValue()
        if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
            if type == .tapDisabledByTimeout { state.disabledByTimeout() }
            state.reenable()
        } else {
            dispatch(type, event: event, engine: state.engine)
        }
        return Unmanaged.passUnretained(event)
    }
}
