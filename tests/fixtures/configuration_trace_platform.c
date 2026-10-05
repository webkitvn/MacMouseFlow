// System-boundary fixture: never installs or posts a real event tap/input.
#include <ApplicationServices/ApplicationServices.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>

struct fake_tap {
    CFMachPortRef port;
    CFRunLoopTimerRef timer;
    CGEventTapCallBack callback;
    void *info;
    _Atomic bool enabled;
};
static struct fake_tap taps[16];
static _Atomic unsigned count;

static void receive(CFMachPortRef port, void *message, CFIndex size, void *info) {
    (void)port; (void)message; (void)size; (void)info;
}
static void input(CFRunLoopTimerRef timer, void *info) {
    (void)timer;
    struct fake_tap *tap = info;
    if (!atomic_load(&tap->enabled)) return;
    CGEventRef event = CGEventCreateScrollWheelEvent(NULL, kCGScrollEventUnitLine, 2, 100, 100);
    tap->callback((CGEventTapProxy)1, kCGEventScrollWheel, event, tap->info);
    const char *path = getenv("MMF_TEST_NATIVE_OUTPUT");
    if (path) {
        FILE *file = fopen(path, "a");
        if (file) {
            fprintf(file, "%.0f %.0f\n", CGEventGetDoubleValueField(event, kCGScrollWheelEventFixedPtDeltaAxis2) * 100,
                    CGEventGetDoubleValueField(event, kCGScrollWheelEventFixedPtDeltaAxis1) * 100);
            fclose(file);
        }
    }
    CFRelease(event);
}
static Boolean trusted(void) { return true; }
static CFMachPortRef create(CGEventTapLocation location, CGEventTapPlacement placement,
                           CGEventTapOptions options, CGEventMask mask,
                           CGEventTapCallBack callback, void *info) {
    (void)location; (void)placement; (void)options; (void)mask;
    if (getenv("MMF_TEST_TAP_FAILURE")) {
        const char *path = getenv("MMF_TEST_NATIVE_OUTPUT");
        FILE *file = path ? fopen(path, "a") : NULL;
        if (file) { fputs("tap_creation_failed\n", file); fclose(file); }
        return NULL;
    }
    unsigned index = atomic_load(&count);
    if (index >= 16) abort();
    struct fake_tap *tap = &taps[index];
    tap->callback = callback; tap->info = info;
    tap->port = CFMachPortCreate(NULL, receive, NULL, NULL);
    atomic_init(&tap->enabled, false);
    CFRunLoopTimerContext context = {0, tap, NULL, NULL, NULL};
    tap->timer = CFRunLoopTimerCreate(NULL, CFAbsoluteTimeGetCurrent() + 0.01, 0.01, 0, 0, input, &context);
    CFRunLoopAddTimer(CFRunLoopGetCurrent(), tap->timer, kCFRunLoopCommonModes);
    atomic_store(&count, index + 1);
    return tap->port;
}
static void enable(CFMachPortRef port, bool enabled) {
    for (unsigned i = atomic_load(&count); i-- > 0;) if (taps[i].port == port) {
        atomic_store(&taps[i].enabled, enabled);
        if (!enabled && taps[i].timer) { CFRunLoopTimerInvalidate(taps[i].timer); CFRelease(taps[i].timer); taps[i].timer = NULL; }
        return;
    }
    abort();
}
static bool is_enabled(CFMachPortRef port) {
    for (unsigned i = atomic_load(&count); i-- > 0;) if (taps[i].port == port) return atomic_load(&taps[i].enabled);
    return false;
}
#define INTERPOSE(replacement, original) \
    __attribute__((used)) static const struct { const void *replacement; const void *original; } \
    binding_##original __attribute__((section("__DATA,__interpose"))) = { (const void *)&replacement, (const void *)&original }
INTERPOSE(trusted, AXIsProcessTrusted);
INTERPOSE(create, CGEventTapCreate);
INTERPOSE(enable, CGEventTapEnable);
INTERPOSE(is_enabled, CGEventTapIsEnabled);

#ifdef MMF_TEST_REUSED_PORT
#include <assert.h>
int main(void) {
    CFMachPortRef reused = (CFMachPortRef)(uintptr_t)1;
    taps[0].port = taps[1].port = reused;
    atomic_store(&count, 2);
    enable(reused, true);
    assert(!atomic_load(&taps[0].enabled));
    assert(atomic_load(&taps[1].enabled));
    assert(is_enabled(reused));
    atomic_store(&taps[0].enabled, true);
    enable(reused, false);
    assert(atomic_load(&taps[0].enabled));
    assert(!is_enabled(reused));
    return 0;
}
#endif
