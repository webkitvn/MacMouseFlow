import AppKit
import Bridge
import CoreGraphics
import Foundation

public enum ScrollAdapter {
    // Numeric result avoids callback-side String construction.
    @discardableResult public static func process(_ event: CGEvent, engine: PointerInputEngine) -> UInt8 {
        guard event.type == .scrollWheel, event.getIntegerValueField(.scrollWheelEventIsContinuous) == 0 else { return 0 }
        guard let decision = engine.evaluate(
            horizontal: event.getIntegerValueField(.scrollWheelEventDeltaAxis2),
            vertical: event.getIntegerValueField(.scrollWheelEventDeltaAxis1)
        ) else { return 2 }
        guard case let .replace(horizontal, vertical) = decision else { return 0 }
        event.setIntegerValueField(.scrollWheelEventDeltaAxis1, value: vertical)
        event.setIntegerValueField(.scrollWheelEventDeltaAxis2, value: horizontal)
        return 1
    }
}

final class TapState: @unchecked Sendable {
    // This lock serializes public lifecycle calls only. The callback never takes it.
    private let lock = NSLock()
    let engine: PointerInputEngine
    let trace = TracePipeline()
    let ready = DispatchSemaphore(value: 0)
    let stopped = DispatchSemaphore(value: 0)
    private var lifecycle = Lifecycle.idle
    private var runLoop: CFRunLoop?
    private var timeoutCount = 0
    private var tap: CFMachPort?
    private var source: CFRunLoopSource?

    private enum Lifecycle { case idle, starting, running, cancelling, finished }

    init(engine: PointerInputEngine) { self.engine = engine }

    func begin() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        guard lifecycle == .idle else { return false }
        lifecycle = .starting
        return true
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
            trace?.enqueue(granularity: 0, decision: 0, outcome: 0, reason: 0, now: DispatchTime.now().uptimeNanoseconds, kind: 1)
            ready.signal()
            complete()
            return
        }
        guard let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0) else {
            trace?.enqueue(granularity: 0, decision: 0, outcome: 0, reason: 4, now: DispatchTime.now().uptimeNanoseconds, kind: 1)
            CGEvent.tapEnable(tap: tap, enable: false)
            CFMachPortInvalidate(tap)
            ready.signal()
            complete()
            return
        }
        self.tap = tap
        self.source = source
        CFRunLoopAddSource(runLoop, source, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)
        lock.lock()
        let shouldRun = lifecycle == .starting && CGEvent.tapIsEnabled(tap: tap)
        lifecycle = shouldRun ? .running : .cancelling
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
        switch lifecycle {
        case .idle, .finished: return (false, nil)
        case .starting, .running: lifecycle = .cancelling
        case .cancelling: break
        }
        return (true, runLoop)
    }

    func awaitReady() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return lifecycle == .running
    }

    func completedTimeoutCount() -> Int {
        lock.lock()
        defer { lock.unlock() }
        precondition(lifecycle == .finished)
        return timeoutCount
    }

    func finishOnOwnerRunLoop() {
        if let tap { CGEvent.tapEnable(tap: tap, enable: false) }
        if let source { CFRunLoopRemoveSource(CFRunLoopGetCurrent(), source, .commonModes) }
        if let tap { CFMachPortInvalidate(tap) }
        source = nil
        tap = nil
        lock.lock()
        runLoop = nil
        lock.unlock()
    }

    func disabledByTimeout() {
        timeoutCount += 1
        trace?.enqueue(granularity: 0, decision: 0, outcome: 0, reason: 1, now: DispatchTime.now().uptimeNanoseconds, kind: 1)
    }
    func reenable() {
        if let tap { CGEvent.tapEnable(tap: tap, enable: true) }
        trace?.enqueue(granularity: 0, decision: 0, outcome: 0, reason: 2, now: DispatchTime.now().uptimeNanoseconds, kind: 1)
    }

    func complete() {
        lock.lock()
        guard lifecycle != .finished else {
            lock.unlock()
            return
        }
        lifecycle = .finished
        runLoop = nil
        trace?.close()
        lock.unlock()
        stopped.signal()
    }
}

@_spi(Benchmark) public final class CallbackHarness {
    private let state: TapState

    @_spi(Benchmark) public init(engine: PointerInputEngine) { state = TapState(engine: engine) }

    @_spi(Benchmark) public func invoke(_ type: CGEventType, event: CGEvent) {
        _ = ScrollRuntime.callback(OpaquePointer(bitPattern: 0x1)!, type, event, Unmanaged.passUnretained(state).toOpaque())
    }

    @_spi(Benchmark) public func setReverse(_ reverse: Bool) -> Bool {
        reverse ? state.engine.setReverseDirection() : state.engine.setSystemDirection()
    }
}

public final class ScrollRuntime {
    private let state: TapState
    private let thread: Thread
    private let coordinatorLock = NSLock()
    private var joined = false

    public init?(reverseForHarness: Bool = false) {
        guard AXIsProcessTrusted(), let engine = PointerInputEngine() else { return nil }
        guard reverseForHarness ? engine.setReverseDirection() : engine.setSystemDirection() else { return nil }
        let state = TapState(engine: engine)
        self.state = state
        thread = Thread { state.run() }
        thread.name = "MacMouseFlow CGEventTap"
    }

    public func start() -> Bool {
        coordinatorLock.lock()
        defer { coordinatorLock.unlock() }
        guard !joined, state.begin() else { return false }
        thread.start()
        guard state.ready.wait(timeout: .now() + 1) == .success else {
            stopLocked()
            return false
        }
        return state.awaitReady()
    }

    public func stop() {
        coordinatorLock.lock()
        defer { coordinatorLock.unlock() }
        stopLocked()
    }

    private func stopLocked() {
        guard !joined else { return }
        let request = state.cancelAndRunLoop()
        guard request.join else {
            joined = true
            return
        }
        if let runLoop = request.runLoop {
            CFRunLoopPerformBlock(runLoop, CFRunLoopMode.defaultMode.rawValue as NSString) {
                self.state.finishOnOwnerRunLoop()
                CFRunLoopStop(runLoop)
            }
            CFRunLoopWakeUp(runLoop)
        }
        _ = state.stopped.wait(timeout: .distantFuture)
        joined = true
    }

    public var disabledByTimeoutCount: Int {
        precondition(joined)
        return state.completedTimeoutCount()
    }

    deinit { stop() }

    fileprivate static let callback: CGEventTapCallBack = { _, type, event, info in
        guard let info else { return Unmanaged.passUnretained(event) }
        let state = Unmanaged<TapState>.fromOpaque(info).takeUnretainedValue()
        if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
            if type == .tapDisabledByTimeout { state.disabledByTimeout() }
            state.reenable()
        } else {
            let lineBased = event.type == .scrollWheel && event.getIntegerValueField(.scrollWheelEventIsContinuous) == 0
            let code = ScrollAdapter.process(event, engine: state.engine)
            state.trace?.enqueue(
                granularity: lineBased ? 1 : 0,
                decision: code,
                outcome: code == 1 ? 1 : 0,
                reason: lineBased ? (code == 1 ? 2 : (code == 2 ? 3 : 1)) : 0,
                now: DispatchTime.now().uptimeNanoseconds
            )
        }
        return Unmanaged.passUnretained(event)
    }
}
