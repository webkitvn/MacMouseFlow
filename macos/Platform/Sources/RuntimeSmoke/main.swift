import CoreFoundation
import Foundation
import Platform

let duration = ProcessInfo.processInfo.environment["MMF_SMOKE_SECONDS"] ?? "10"
guard let seconds = Double(duration), seconds.isFinite, (0.01...60).contains(seconds) else {
    fputs("MMF_SMOKE_SECONDS must be finite and between 0.01 and 60\n", stderr)
    exit(1)
}

func observe(_ message: String) {
    print(message)
    fflush(stdout)
    CFRunLoopRunInMode(.defaultMode, seconds, false)
}

func activePhase(_ phase: String) {
    guard let runtime = ScrollRuntime(direction: .reverse, amountPercent: 137) else {
        fputs("\(phase): Accessibility permission or engine unavailable; physical fail-open observation required\n", stderr)
        exit(1)
    }
    guard runtime.start(), runtime.status == .active else {
        runtime.stop()
        fputs("\(phase): CGEventTap startup unavailable; physical fail-open observation required\n", stderr)
        exit(1)
    }
    observe("\(phase): active for \(seconds)s, reverse direction, Scroll Amount 137%. Physically verify LineBased reversal/increased magnitude and PixelBased preservation.")
    let wasActive = runtime.status == .active
    runtime.stop()
    guard wasActive, runtime.status == .unavailable, !runtime.start() else {
        fputs("\(phase): lifecycle assertion failed\n", stderr)
        exit(1)
    }
    let timeouts = runtime.disabledByTimeoutCount
    print("\(phase): stopped/unavailable; tapDisabledByTimeout count: \(timeouts)")
    guard timeouts == 0 else { exit(1) }
}

activePhase("start")
observe("stopped: no smoke tap for \(seconds)s. Physically verify original scrolling resumes with no stuck transform.")
// ScrollRuntime is single-use; recovery creates a fresh runtime, as InputRuntime does.
activePhase("restart")
print("Lifecycle assertions passed; physical input, fail-open and permission/tap recovery observations remain operator evidence. Synthetic gestures are not physical proof.")
