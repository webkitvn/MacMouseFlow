// System-boundary fixture: never installs or posts a real event tap/input.
#include <ApplicationServices/ApplicationServices.h>
#include <fcntl.h>
#include <limits.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct fake_tap {
    CFMachPortRef port;
    CFRunLoopTimerRef timer;
    CGEventTapCallBack callback;
    void *info;
    _Atomic bool enabled;
};
static struct fake_tap taps[16];
static _Atomic unsigned count;
static _Atomic bool stalling;

static int trace_segment(int fd) {
    char path[PATH_MAX] = {0};
    return fcntl(fd, F_GETPATH, path) == 0 && strstr(path, "/trace-1.jsonl") != NULL;
}

static void stall_trace_write(int fd, const void *buffer, size_t length) {
    const char *started = getenv("MMF_TEST_TRACE_STALL_STARTED");
    const char *release = getenv("MMF_TEST_TRACE_STALL_RELEASE");
    if (!started || !release || !getenv("MMF_TEST_TRACE_STALL") || !trace_segment(fd)) return;
    bool expected = false;
    if (!atomic_compare_exchange_strong(&stalling, &expected, true)) return;
    int marker = open(started, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (marker >= 0) close(marker);
    while (access(release, F_OK) != 0) usleep(1000);
    if (getenv("MMF_TEST_TRACE_SLOW_DRAIN")) usleep(6000000);
    (void)buffer; (void)length;
}

ssize_t stall_write(int fd, const void *buffer, size_t length) {
    stall_trace_write(fd, buffer, length);
    return write(fd, buffer, length);
}

static void receive(CFMachPortRef port, void *message, CFIndex size, void *info) {
    (void)port; (void)message; (void)size; (void)info;
}
static void input(CFRunLoopTimerRef timer, void *info) {
    (void)timer;
    struct fake_tap *tap = info;
    if (!atomic_load(&tap->enabled)) return;
    unsigned events = getenv("MMF_TEST_TRACE_STALL") ? 140000 : 1;
    unsigned mismatches = 0;
    CGEventRef event = CGEventCreateScrollWheelEvent(NULL, kCGScrollEventUnitLine, 2, 100, 100);
    if (!event) return;
    for (unsigned index = 0; index < events; ++index) {
        CGEventSetIntegerValueField(event, kCGScrollWheelEventDeltaAxis1, 100);
        CGEventSetIntegerValueField(event, kCGScrollWheelEventDeltaAxis2, 100);
        tap->callback((CGEventTapProxy)1, kCGEventScrollWheel, event, tap->info);
        if (getenv("MMF_TEST_TRACE_STALL_CORRUPT_EARLY") && index + 1 < events) {
            CGEventSetDoubleValueField(event, kCGScrollWheelEventFixedPtDeltaAxis2, 0);
            CGEventSetDoubleValueField(event, kCGScrollWheelEventFixedPtDeltaAxis1, 0);
        }
        double horizontal = CGEventGetDoubleValueField(event, kCGScrollWheelEventFixedPtDeltaAxis2) * 100;
        double vertical = CGEventGetDoubleValueField(event, kCGScrollWheelEventFixedPtDeltaAxis1) * 100;
        if (horizontal != -13700 || vertical != -13700) ++mismatches;
        const char *path = getenv("MMF_TEST_NATIVE_OUTPUT");
        if (path && index + 1 == events) {
            FILE *file = fopen(path, "a");
            if (file) { fprintf(file, "%.0f %.0f\n", horizontal, vertical); fclose(file); }
        }
    }
    CFRelease(event);
    const char *summary = getenv("MMF_TEST_TRACE_STALL_SUMMARY");
    if (summary) { FILE *file = fopen(summary, "w"); if (file) { fprintf(file, "%u %u\n", events, mismatches); fclose(file); } }
    const char *done = getenv("MMF_TEST_TRACE_STALL_CALLBACKS_DONE");
    if (done) { int marker = open(done, O_WRONLY | O_CREAT | O_TRUNC, 0600); if (marker >= 0) close(marker); }
}
static Boolean trusted(void) { return getenv("MMF_TEST_UNTRUSTED") ? false : true; }
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
        const char *receipt = getenv("MMF_TEST_TAP_TEARDOWN");
        if (!enabled && receipt) {
            unsigned active = 0;
            for (unsigned index = 0; index < atomic_load(&count); ++index) {
                if (atomic_load(&taps[index].enabled) || taps[index].timer) ++active;
            }
            FILE *file = fopen(receipt, "a");
            if (file) { fprintf(file, "disabled active=%u timer=%d\n", active, taps[i].timer != NULL); fclose(file); }
        }
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
INTERPOSE(stall_write, write);

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
