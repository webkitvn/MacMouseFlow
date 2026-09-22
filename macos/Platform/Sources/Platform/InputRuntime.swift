import ApplicationServices
import Combine
import Foundation

public enum InputRuntimeState: Equatable {
    case off
    case needsAccessibilityAccess
    case active
    case inputUnavailable
    case configurationNeedsAttention

    public static func resolve(enabled: Bool, accessibilityTrusted: Bool, runtimeStatus: ScrollRuntimeStatus, attention: ConfigurationAttention) -> Self {
        guard attention != .malformed, attention != .newerSchema else { return .configurationNeedsAttention }
        guard enabled else { return .off }
        guard accessibilityTrusted else { return .needsAccessibilityAccess }
        return runtimeStatus == .active ? .active : .inputUnavailable
    }
}

public final class InputRuntime: ObservableObject {
    @Published public private(set) var state: InputRuntimeState = .off
    @Published public private(set) var configuration: PersistedConfiguration
    @Published public private(set) var configurationAttention: ConfigurationAttention
    @Published public private(set) var isSaving = false

    private let store: ConfigurationStore
    private let lifecycle = LifecycleExecutor()
    private var accessibilityTrusted = false
    private var runtimeStatus: ScrollRuntimeStatus = .unavailable
    private var monitor: Timer?
    private var revision: UInt64 = 0

    public init(store: ConfigurationStore = ConfigurationStore()) {
        self.store = store
        (configuration, configurationAttention) = store.load()
        lifecycle.onStatus = { [weak self] status in
            guard let self else { return }
            self.runtimeStatus = status
            self.publishState()
        }
        reconcileIntent()
    }

    public var hasAccessibilityAccess: Bool { AXIsProcessTrusted() }
    public var canEditConfiguration: Bool { (configurationAttention == .none || configurationAttention == .saveFailed) && !isSaving }

    public func setEnabled(_ enabled: Bool) { commit(.init(enabled: enabled, direction: configuration.direction)) }
    public func setDirection(_ direction: ScrollDirection) { commit(.init(enabled: configuration.enabled, direction: direction)) }

    public func resetMalformedConfiguration() {
        guard configurationAttention == .malformed || configurationAttention == .saveFailed else { return }
        guard store.persist(.default) else {
            configurationAttention = .saveFailed
            publishState()
            return
        }
        configuration = .default
        configurationAttention = .none
        revision &+= 1
        runtimeStatus = .unavailable
        reconcileIntent()
    }

    public func refresh() { reconcileIntent() }

    public func requestAccessibilityAccess() {
        AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true] as CFDictionary)
        reconcileIntent()
    }

    deinit {
        monitor?.invalidate()
        lifecycle.shutdown()
    }

    private func commit(_ candidate: PersistedConfiguration) {
        guard canEditConfiguration, candidate != configuration else { return }
        guard validate(direction: candidate.direction), store.persist(candidate) else {
            configurationAttention = .saveFailed
            publishState()
            return
        }
        configuration = candidate
        configurationAttention = .none
        revision &+= 1
        runtimeStatus = .unavailable
        isSaving = false
        reconcileIntent()
    }

    private func reconcileIntent() {
        accessibilityTrusted = AXIsProcessTrusted()
        let canRun = configurationAttention != .malformed && configurationAttention != .newerSchema
        if configuration.enabled, canRun, monitor == nil {
            monitor = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.refresh() }
        } else if (!configuration.enabled || !canRun), let monitor {
            monitor.invalidate()
            self.monitor = nil
        }
        publishState()
        lifecycle.request(enabled: configuration.enabled && canRun, trusted: accessibilityTrusted, direction: configuration.direction, revision: revision)
    }

    private func publishState() {
        state = .resolve(enabled: configuration.enabled, accessibilityTrusted: accessibilityTrusted, runtimeStatus: runtimeStatus, attention: configurationAttention)
    }
}

private final class LifecycleExecutor: @unchecked Sendable {
    private struct Intent: Equatable {
        var enabled: Bool
        var trusted: Bool
        var direction: ScrollDirection
        var revision: UInt64
    }

    private let queue = DispatchQueue(label: "io.github.webkitvn.macmouseflow.lifecycle")
    private let lock = NSLock()
    private var intent = Intent(enabled: false, trusted: false, direction: .preserve, revision: 0)
    private var pending = false
    private var draining = false
    private var shutdownRequested = false

    var onStatus: ((ScrollRuntimeStatus) -> Void)?

    private var runtime: ScrollRuntime?
    private var activeRevision: UInt64?
    private var startFailures = 0
    private var nextStartAllowed = DispatchTime.now()

    func request(enabled: Bool, trusted: Bool, direction: ScrollDirection, revision: UInt64) {
        lock.lock()
        guard !shutdownRequested else { lock.unlock(); return }
        intent = Intent(enabled: enabled, trusted: trusted, direction: direction, revision: revision)
        pending = true
        guard !draining else { lock.unlock(); return }
        draining = true
        lock.unlock()
        queue.async { [weak self] in self?.drain() }
    }

    func shutdown() {
        lock.lock()
        guard !shutdownRequested else { lock.unlock(); return }
        shutdownRequested = true
        pending = false
        intent.enabled = false
        lock.unlock()
        queue.async {
            self.runtime?.stop()
            self.runtime = nil
        }
    }

    private func drain() {
        while true {
            lock.lock()
            guard pending, !shutdownRequested else { draining = false; lock.unlock(); return }
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
        guard desired.enabled, desired.trusted else { retire(); return }
        if let runtime {
            guard activeRevision == desired.revision else {
                runtime.stop()
                self.runtime = nil
                activeRevision = nil
                return reconcile()
            }
            guard runtime.status == .active else {
                runtime.stop()
                self.runtime = nil
                activeRevision = nil
                registerStartFailure()
                publish(.unavailable)
                return
            }
            publish(.active)
            return
        }
        guard DispatchTime.now() >= nextStartAllowed else { publish(.unavailable); return }
        guard let candidate = ScrollRuntime(direction: desired.direction), candidate.start() else {
            registerStartFailure()
            publish(.unavailable)
            return
        }
        let latest = latestIntent()
        guard latest.enabled, latest.trusted, latest.revision == desired.revision, latest.direction == desired.direction, candidate.status == .active else {
            candidate.stop()
            if latest.enabled && latest.trusted { registerStartFailure() } else { resetRetry() }
            publish(.unavailable)
            return
        }
        runtime = candidate
        activeRevision = desired.revision
        resetRetry()
        publish(.active)
    }

    private func retire() {
        runtime?.stop()
        runtime = nil
        activeRevision = nil
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

    private static func backoffDelay(failures: Int) -> DispatchTimeInterval { .seconds(1 << min(failures, 3)) }

    private func publish(_ status: ScrollRuntimeStatus) {
        guard !isShutdown() else { return }
        DispatchQueue.main.async { [weak self] in self?.onStatus?(status) }
    }
}
