import Foundation

private let traceCapacity = 256
private let traceStoreLimit = 64 * 1024 * 1024
private let traceFileLimit = 1024 * 1024
private let traceManifestReserve = 1024

// Fixed numeric fields keep callback tracing allocation-free apart from the queue slot.
private struct TraceRecord {
    let kind: UInt8
    let sequence: UInt64
    let monotonicNanoseconds: UInt64
    let granularity: UInt8
    let decision: UInt8
    let outcome: UInt8
    let reason: UInt8
}

final class TracePipeline: @unchecked Sendable {
    private let runID = UUID().uuidString
    private let started = DispatchTime.now().uptimeNanoseconds
    private let lock = NSLock()
    private var queue = [TraceRecord?](repeating: nil, count: traceCapacity)
    private var readIndex = 0
    private var writeIndex = 0
    private var count = 0
    private var nextSequence: UInt64 = 0
    private var dropped: UInt64 = 0
    private var totalDropped: UInt64 = 0
    // The event-tap callback and close both execute on its single owner thread. A failed
    // tryLock records locally, then the next successful lock folds it into shared drops.
    private var pendingContention: UInt64 = 0
    private var stopping = false
    private let available = DispatchSemaphore(value: 0)
    private let drained = DispatchSemaphore(value: 0)
    private let root: URL
    private let destination: URL
    private var activeBytes = 0

    init?() {
        guard ProcessInfo.processInfo.environment["MMF_TRACE"] == "1" else { return nil }
        root = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support/io.github.webkitvn.macmouseflow/Traces")
        destination = root.appendingPathComponent(runID, isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
            activeBytes = pruneOldRuns()
            try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
            try writeManifest(clean: false, drops: 0)
            activeBytes += directorySize(destination)
            enqueue(granularity: 0, decision: 0, outcome: 0, reason: 3, now: DispatchTime.now().uptimeNanoseconds, kind: 1)
        } catch { return nil }
        Thread { [self] in drain() }.start()
    }

    // tryLock only: diagnostic failure never delays or changes input handling.
    func enqueue(granularity: UInt8, decision: UInt8, outcome: UInt8, reason: UInt8, now: UInt64, kind: UInt8 = 0) {
        guard lock.try() else { pendingContention &+= 1; return }
        defer { lock.unlock() }
        dropped &+= pendingContention
        totalDropped &+= pendingContention
        pendingContention = 0
        guard !stopping, count < traceCapacity else { dropped &+= 1; totalDropped &+= 1; return }
        nextSequence &+= 1
        queue[writeIndex] = TraceRecord(kind: kind, sequence: nextSequence, monotonicNanoseconds: now, granularity: granularity, decision: decision, outcome: outcome, reason: reason)
        writeIndex = (writeIndex + 1) % traceCapacity
        count += 1
        available.signal()
    }

    func close() {
        lock.lock()
        dropped &+= pendingContention
        totalDropped &+= pendingContention
        pendingContention = 0
        stopping = true
        lock.unlock()
        available.signal()
        _ = drained.wait(timeout: .now() + 2)
    }

    private func take() -> (TraceRecord?, UInt64, Bool) {
        lock.lock()
        defer { lock.unlock() }
        let shouldStop = stopping && count == 0
        guard count > 0 else { return (nil, 0, shouldStop) }
        let record = queue[readIndex]
        queue[readIndex] = nil
        readIndex = (readIndex + 1) % traceCapacity
        count -= 1
        let losses = dropped
        dropped = 0
        return (record, losses, false)
    }

    private func drain() {
        var index = 0, segmentBytes = 0
        var handle: FileHandle?
        var sinkFailed = false
        while true {
            _ = available.wait(timeout: .now() + 1)
            while true {
                let (record, losses, shouldStop) = take()
                if shouldStop {
                    lock.lock()
                    let finalDrops = totalDropped
                    let pendingDrops = dropped
                    lock.unlock()
                    if pendingDrops > 0 { writeDrop(pendingDrops, handle: &handle, index: &index, bytes: &segmentBytes, sinkFailed: &sinkFailed) }
                    if sinkFailed == false { write(["schema_version": 1, "run_id": runID, "sequence": UInt64.max, "kind": "lifecycle", "monotonic_ns": DispatchTime.now().uptimeNanoseconds, "reason_code": "stopped"], handle: &handle, index: &index, bytes: &segmentBytes, sinkFailed: &sinkFailed) }
                    try? handle?.close()
                    try? writeManifest(clean: !sinkFailed, drops: finalDrops)
                    drained.signal()
                    return
                }
                guard let record else { break }
                if losses > 0 { writeDrop(losses, handle: &handle, index: &index, bytes: &segmentBytes, sinkFailed: &sinkFailed) }
                let object: [String: Any] = record.kind == 0
                    ? ["schema_version": 1, "run_id": runID, "sequence": record.sequence, "kind": "input", "monotonic_ns": record.monotonicNanoseconds, "granularity": record.granularity == 1 ? "line_based" : "pixel_based", "decision": decisionName(record.decision), "native_outcome": outcomeName(record.outcome), "reason_code": reasonName(record.reason)]
                    : ["schema_version": 1, "run_id": runID, "sequence": record.sequence, "kind": "lifecycle", "monotonic_ns": record.monotonicNanoseconds, "reason_code": lifecycleReasonName(record.reason)]
                write(object, handle: &handle, index: &index, bytes: &segmentBytes, sinkFailed: &sinkFailed)
            }
        }
    }

    private func writeDrop(_ losses: UInt64, handle: inout FileHandle?, index: inout Int, bytes: inout Int, sinkFailed: inout Bool) {
        write(["schema_version": 1, "run_id": runID, "kind": "trace.dropped", "drop_count": losses], handle: &handle, index: &index, bytes: &bytes, sinkFailed: &sinkFailed)
    }
    private func write(_ object: [String: Any], handle: inout FileHandle?, index: inout Int, bytes: inout Int, sinkFailed: inout Bool) {
        guard !sinkFailed, let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]), data.count + 1 <= traceFileLimit else { sinkFailed = true; return }
        guard activeBytes + data.count + 1 + traceManifestReserve <= traceStoreLimit else { sinkFailed = true; return }
        if handle == nil || bytes + data.count + 1 > traceFileLimit {
            try? handle?.close()
            let path = destination.appendingPathComponent("trace-\(index).jsonl")
            FileManager.default.createFile(atPath: path.path, contents: nil)
            handle = FileHandle(forWritingAtPath: path.path)
            index += 1; bytes = 0
        }
        guard let handle else { sinkFailed = true; return }
        do { try handle.write(contentsOf: data); try handle.write(contentsOf: Data([10])); bytes += data.count + 1; activeBytes += data.count + 1 } catch { sinkFailed = true }
    }

    private func writeManifest(clean: Bool, drops: UInt64) throws {
        let data = try JSONSerialization.data(withJSONObject: ["schema_version": 1, "run_id": runID, "started_monotonic_ns": started, "clean_shutdown": clean, "drop_count": drops], options: [.sortedKeys])
        try data.write(to: destination.appendingPathComponent("manifest.json"), options: .atomic)
    }
    @discardableResult private func pruneOldRuns() -> Int {
        let runs = (try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: [.contentModificationDateKey], options: [.skipsHiddenFiles])) ?? []
        var size = runs.reduce(0) { $0 + directorySize($1) }
        // Reserve manifest space before creating the current run.
        for run in runs.sorted(by: { ((try? $0.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast) < ((try? $1.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast) }) where size + traceManifestReserve > traceStoreLimit {
            let old = directorySize(run); try? FileManager.default.removeItem(at: run); size -= old
        }
        return size
    }
    private func directorySize(_ url: URL) -> Int {
        guard let enumerator = FileManager.default.enumerator(at: url, includingPropertiesForKeys: [.fileSizeKey]) else { return 0 }
        return enumerator.reduce(0) { total, item in total + ((try? (item as? URL)?.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0) }
    }
}
private func decisionName(_ value: UInt8) -> String { ["preserve", "replace", "engine_unavailable"][Int(value)] }
private func outcomeName(_ value: UInt8) -> String { ["preserved", "applied"][Int(value)] }
private func reasonName(_ value: UInt8) -> String { ["not_line_based", "preserve", "replace", "engine_unavailable"][Int(value)] }
private func lifecycleReasonName(_ value: UInt8) -> String { ["tap_unavailable", "disabled_by_timeout", "reenabled", "started", "source_unavailable"][Int(value)] }
