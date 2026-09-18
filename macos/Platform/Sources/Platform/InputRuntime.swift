import ApplicationServices
import Combine

public enum InputRuntimeState: Equatable {
    case off
    case needsAccessibilityAccess
    case active
    case inputUnavailable
    case configurationNeedsAttention

    static func resolve(enabled: Bool, accessibilityTrusted: Bool, runtimeStatus: ScrollRuntimeStatus) -> Self {
        guard enabled else { return .off }
        guard accessibilityTrusted else { return .needsAccessibilityAccess }
        switch runtimeStatus {
        case .active: return .active
        case .unavailable: return .inputUnavailable
        }
    }
}

public final class InputRuntime: ObservableObject {
    @Published public private(set) var state: InputRuntimeState = .off
    private var runtime: ScrollRuntime?
    private var enabled = false
    private var monitor: Timer?

    public init() {}

    public var hasAccessibilityAccess: Bool { AXIsProcessTrusted() }

    public func setEnabled(_ enabled: Bool) {
        self.enabled = enabled
        if enabled {
            if monitor == nil {
                monitor = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.refresh() }
            }
        } else {
            monitor?.invalidate()
            monitor = nil
            runtime?.stop()
            runtime = nil
        }
        refresh()
    }

    public func refresh() {
        let accessibilityTrusted = AXIsProcessTrusted()
        if runtime?.status == .unavailable {
            runtime?.stop()
            runtime = nil
        }
        if enabled && accessibilityTrusted && runtime == nil, let candidate = ScrollRuntime(), candidate.start() {
            runtime = candidate
        }
        if !accessibilityTrusted {
            runtime?.stop()
            runtime = nil
        }
        update(accessibilityTrusted: accessibilityTrusted, runtimeStatus: runtime?.status ?? .unavailable)
    }

    public func update(accessibilityTrusted: Bool, runtimeStatus: ScrollRuntimeStatus) {
        state = .resolve(enabled: enabled, accessibilityTrusted: accessibilityTrusted, runtimeStatus: runtimeStatus)
    }

    deinit { monitor?.invalidate() }

    public func requestAccessibilityAccess() {
        AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true] as CFDictionary)
        refresh()
    }
}
