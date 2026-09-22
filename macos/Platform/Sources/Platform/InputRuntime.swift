import ApplicationServices
import Combine
import Foundation

public enum InputRuntimeState: Equatable {
    case off
    case needsAccessibilityAccess
    case active
    case inputUnavailable
    case configurationNeedsAttention

    /// The single state contract shared by the runtime and the UI: given the user's
    /// intent (`enabled`), current Accessibility trust, and the lifecycle executor's
    /// last observed tap status, what should the UI show?
    public static func resolve(enabled: Bool, accessibilityTrusted: Bool, runtimeStatus: ScrollRuntimeStatus) -> Self {
        guard enabled else { return .off }
        guard accessibilityTrusted else { return .needsAccessibilityAccess }
        switch runtimeStatus {
        case .active: return .active
        case .unavailable: return .inputUnavailable
        }
    }
}

/// Main/UI-facing runtime facade.
///
/// This type records desired intent and publishes observable state; it never performs
/// blocking `ScrollRuntime` lifecycle work itself. All create/start/stop reconciliation
/// runs on a private serialized lifecycle executor, so the UI thread cannot be blocked
/// by a one-second `start()` wait or an indefinite `stop()` join.
public final class InputRuntime: ObservableObject {
    @Published public private(set) var state: InputRuntimeState = .off

    private let lifecycle = LifecycleExecutor()
    private var enabled = false
    private var accessibilityTrusted = false
    private var runtimeStatus: ScrollRuntimeStatus = .unavailable
    private var monitor: Timer?

    public init() {
        lifecycle.onStatus = { [weak self] status in
            guard let self else { return }
            self.runtimeStatus = status
            self.publishState()
        }
    }

    public var hasAccessibilityAccess: Bool { AXIsProcessTrusted() }

    public func setEnabled(_ enabled: Bool) {
        if self.enabled != enabled {
            // A new episode: no lifecycle status is established until the executor
            // reports one, so the UI can never show a stale Active from a prior run.
            runtimeStatus = .unavailable
        }
        self.enabled = enabled
        if enabled {
            if monitor == nil {
                monitor = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.refresh() }
            }
        } else {
            monitor?.invalidate()
            monitor = nil
        }
        reconcileIntent()
    }

    public func refresh() { reconcileIntent() }

    public func requestAccessibilityAccess() {
        AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true] as CFDictionary)
        reconcileIntent()
    }

    deinit {
        monitor?.invalidate()
        // Never tear a live `ScrollRuntime` down on the releasing (UI) thread: hand the
        // executor an asynchronous, serialized shutdown that retains the executor and
        // its runtime until the serial queue retires them.
        lifecycle.shutdown()
    }

    /// Sample the inputs the UI owns, publish from what is already known, and hand the
    /// desired intent to the lifecycle executor without waiting for any transition.
    private func reconcileIntent() {
        accessibilityTrusted = AXIsProcessTrusted()
        publishState()
        lifecycle.request(enabled: enabled, trusted: accessibilityTrusted)
    }

    private func publishState() {
        state = .resolve(enabled: enabled, accessibilityTrusted: accessibilityTrusted, runtimeStatus: runtimeStatus)
    }
}

/// Private serialized executor for `ScrollRuntime` create/start/stop reconciliation.
///
/// Main/UI records intent; this executor owns the only strong reference to the
/// `ScrollRuntime` and drives the synchronous `start()` (readiness wait) and `stop()`
/// (thread join) barriers off the UI thread. Requests coalesce to the latest recorded
/// intent — at most one transition runs at a time and timer/UI events are never
/// replayed FIFO. Failed starts are retried with bounded exponential backoff, and the
/// retry policy resets only after a verified `.active` tap or when the desire to run
/// is withdrawn. Teardown is an executor-owned asynchronous shutdown, so no caller
/// ever releases a live runtime on its own thread.
private final class LifecycleExecutor: @unchecked Sendable {
    // `intent`/`pending`/`draining`/`shutdownRequested` are guarded by `lock`; every other
    // property is confined to the serial `queue` (or, for `onStatus`, set before first
    // use and read on the main queue), which is why `@unchecked Sendable` is safe here.
    private struct Intent { var enabled: Bool; var trusted: Bool }

    private let queue = DispatchQueue(label: "io.github.webkitvn.macmouseflow.lifecycle")
    private let lock = NSLock()
    private var intent = Intent(enabled: false, trusted: false)
    private var pending = false
    private var draining = false
    private var shutdownRequested = false

    /// Delivered on the main queue whenever the observed status changes.
    var onStatus: ((ScrollRuntimeStatus) -> Void)?

    private var runtime: ScrollRuntime?
    private var startFailures = 0
    private var nextStartAllowed = DispatchTime.now()

    /// Records intent and schedules reconciliation. Ignored once shutdown has been
    /// submitted, so a queued request can never revive a shut-down executor.
    func request(enabled: Bool, trusted: Bool) {
        lock.lock()
        guard !shutdownRequested else {
            lock.unlock()
            return
        }
        intent = Intent(enabled: enabled, trusted: trusted)
        pending = true
        if draining {
            // A drain is already running; it will pick up this latest intent itself.
            lock.unlock()
            return
        }
        draining = true
        lock.unlock()
        queue.async { [weak self] in self?.drain() }
    }

    /// Asynchronous, serialized teardown. The submitted block captures `self`
    /// strongly, so the executor and its runtime stay alive until the serial queue
    /// retires them. The caller (e.g. `InputRuntime.deinit`) never waits and never
    /// releases a live runtime on its own thread.
    func shutdown() {
        lock.lock()
        guard !shutdownRequested else {
            lock.unlock()
            return
        }
        shutdownRequested = true
        // Clear pending intent so an already-scheduled drain cannot reconcile — and
        // therefore cannot start a runtime — after shutdown.
        pending = false
        intent = Intent(enabled: false, trusted: false)
        lock.unlock()
        queue.async {
            if let runtime = self.runtime {
                runtime.stop()
                self.runtime = nil
            }
        }
    }

    private func drain() {
        while true {
            lock.lock()
            guard pending, !shutdownRequested else {
                draining = false
                lock.unlock()
                return
            }
            pending = false
            lock.unlock()
            reconcile()
        }
    }

    private func latestIntent() -> Intent {
        lock.lock()
        defer { lock.unlock() }
        return intent
    }

    private func isShutdown() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return shutdownRequested
    }

    private func reconcile() {
        guard !isShutdown() else { return }
        let desired = latestIntent()
        guard desired.enabled, desired.trusted else {
            retireIntentWithdrawn()
            return
        }
        if let runtime {
            guard runtime.status == .unavailable else {
                publish(runtime.status)
                return
            }
            // The live tap went unavailable. `stop()` joins synchronously here, then a
            // retry delay is registered so the next tick cannot immediately churn a
            // replacement thread/trace. The replacement waits for the backoff gate.
            runtime.stop()
            self.runtime = nil
            registerStartFailure()
            publish(.unavailable)
            return
        }
        guard DispatchTime.now() >= nextStartAllowed else {
            // Bounded retry: during backoff do not create a runtime/thread/trace.
            publish(.unavailable)
            return
        }
        guard let candidate = ScrollRuntime(), candidate.start() else {
            registerStartFailure()
            publish(.unavailable)
            return
        }
        // Disable or permission loss can land while `start()` blocks on this executor.
        // Latest intent wins: retire the stale candidate instead of publishing Active.
        let latest = latestIntent()
        guard latest.enabled, latest.trusted else {
            candidate.stop()
            resetRetry()
            publish(.unavailable)
            return
        }
        // Retry state resets only on a verified Active tap; a candidate that is already
        // unavailable keeps the bounded-retry delay rather than counting as success.
        guard candidate.status == .active else {
            candidate.stop()
            registerStartFailure()
            publish(.unavailable)
            return
        }
        runtime = candidate
        resetRetry()
        publish(.active)
    }

    /// Disabling or trust removal withdraws the desire to run: the running runtime is
    /// retired and the retry policy starts a fresh episode.
    private func retireIntentWithdrawn() {
        if let runtime {
            runtime.stop()
            self.runtime = nil
        }
        resetRetry()
        publish(.unavailable)
    }

    private func registerStartFailure() {
        startFailures += 1
        nextStartAllowed = DispatchTime.now() + Self.backoffDelay(failures: startFailures)
    }

    private func resetRetry() {
        startFailures = 0
        nextStartAllowed = .now()
    }

    private static func backoffDelay(failures: Int) -> DispatchTimeInterval {
        .seconds(1 << min(failures, 3)) // 2s, 4s, 8s, then capped at 8s
    }

    private func publish(_ status: ScrollRuntimeStatus) {
        // Every observation is delivered: episode resets otherwise leave the façade stale (PR #95 N1).
        // No stale callback may outlive shutdown.
        guard !isShutdown() else { return }
        DispatchQueue.main.async { [weak self] in self?.onStatus?(status) }
    }
}
