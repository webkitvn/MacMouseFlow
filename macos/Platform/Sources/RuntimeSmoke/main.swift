import CoreFoundation
import Platform

let seconds: CFTimeInterval = 10

guard let runtime = ScrollRuntime(reverseForHarness: true), runtime.start() else {
    fputs("Accessibility permission or CGEventTap startup unavailable\n", stderr)
    exit(1)
}
guard runtime.status == .active else { exit(1) }
print("Scroll tap active for \(seconds) seconds. Verify LineBased reversal and PixelBased preservation with your input device.")
CFRunLoopRunInMode(.defaultMode, seconds, false)
runtime.stop()
guard runtime.status == .unavailable else { exit(1) }
let timeouts = runtime.disabledByTimeoutCount
print("tapDisabledByTimeout count: \(timeouts)")
if timeouts != 0 { exit(1) }
print("Smoke completed; physical input observations remain operator evidence.")
