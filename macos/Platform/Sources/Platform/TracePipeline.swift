import CPointerInput
import CoreFoundation
import Foundation
import os

// Fixed 131072-record ceiling absorbs the benchmark burst; overflow is explicitly dropped.
private let traceCapacity = 131_072
private let traceStoreLimit = 64 * 1024 * 1024
private let traceFileLimit = 1024 * 1024
private let traceManifestReserve = 2048

// All producer fields are fixed-width scalars. JSON names/strings exist only in drain().
private struct TraceRecord {
    let kind: UInt8
    let sequence: UInt64
    let inputSequence: UInt64
    let tNS: UInt64
    let horizontal: Int64
    let vertical: Int64
    let granularity: UInt8
    let decision: UInt8
    let outcome: UInt8
    let reason: UInt8
    let extractionNS: UInt64
    let rustNS: UInt64
    let applyNS: UInt64
    let totalNS: UInt64
}

// M0 is a single process: this coordinator serializes all in-process trace stores; IPC is unnecessary.
private final class TraceStore: @unchecked Sendable {
    static let shared = TraceStore()
    let lock = NSLock()
    var active = Set<URL>()
    var bytes = [URL: Int]()
    var manifests = [URL: Int]()
    var initializedRoots = Set<URL>()
}

final class TracePipeline: @unchecked Sendable {
    private let runID = UUID().uuidString
    private let started = DispatchTime.now().uptimeNanoseconds
    private let runStartUTC = ISO8601DateFormatter().string(from: Date())
    private let lock = NSLock()
    // Allocated only after the explicit trace-off guard succeeds.
    private var ring: UnsafeMutablePointer<mmf_trace_ring>?
    private var nextSequence: UInt64 = 0
    private var nextPublishSequence: UInt64 = 0
    // Single event-tap callback producer owns this receive counter; increment before tryLock.
    private var nextInputSequence: UInt64 = 0
    private var totalDropped: UInt64 = 0
    // Noncallback lifecycle is a bounded fixed ring; callback lifecycle uses the SPSC ring.
    private var lifecycleQueue = [UInt8](repeating: 0, count: 16)
    private var lifecycleRead = 0, lifecycleWrite = 0, lifecycleCount = 0
    private var stopping = false
    private var closed = false
    private var writerFailed = false
    private let available = DispatchSemaphore(value: 0), drained = DispatchSemaphore(value: 0)
    private let root: URL, destination: URL
    private let logger = Logger(subsystem: "io.github.webkitvn.macmouseflow", category: "diagnostics")

    init?() {
        // M0 is one process; there are no cross-process trace writers. Store accounting is process-local.
        guard ProcessInfo.processInfo.environment["MMF_TRACE"] != "0" else { return nil }
        let configured = ProcessInfo.processInfo.environment["MMF_TRACE_DIR"]
        root = configured.map(URL.init(fileURLWithPath:)) ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support/io.github.webkitvn.macmouseflow/Traces")
        destination = root.appendingPathComponent(runID, isDirectory: true)
        do {
            TraceStore.shared.lock.lock()
            defer { TraceStore.shared.lock.unlock() }
            ring = UnsafeMutablePointer<mmf_trace_ring>.allocate(capacity: 1)
            mmf_trace_ring_init(ring!)
            try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
            // Scan once; later runs preserve outstanding admitted reservations and subtract only deletions.
            if TraceStore.shared.initializedRoots.insert(root).inserted {
                TraceStore.shared.bytes[root] = directorySize(root)
            }
            pruneOldRuns(reserving: traceManifestReserve)
            guard TraceStore.shared.bytes[root, default: 0] + traceManifestReserve <= traceStoreLimit else { throw NSError(domain: "trace", code: 1) }
            try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
            do {
                try writeManifest(clean: false, drops: 0)
                TraceStore.shared.bytes[root, default: 0] += traceManifestReserve
                TraceStore.shared.manifests[destination] = traceManifestReserve
                TraceStore.shared.active.insert(destination)
                try writeStart()
            } catch {
                TraceStore.shared.active.remove(destination)
                TraceStore.shared.bytes[root, default: 0] = max(0, TraceStore.shared.bytes[root, default: 0] - (TraceStore.shared.manifests.removeValue(forKey: destination) ?? 0))
                try? FileManager.default.removeItem(at: destination)
                throw error
            }
        } catch { return nil }
        Thread { [self] in drain() }.start()
    }

    deinit { ring?.deallocate() }

    // One event-tap producer; atomic push never locks or blocks.
    func enqueue(horizontal: Int64, vertical: Int64, granularity: UInt8, decision: UInt8, outcome: UInt8, reason: UInt8, extractionNS: UInt64, rustNS: UInt64, applyNS: UInt64, totalNS: UInt64, tNS: UInt64, kind: UInt8 = 0) {
        // Input sequence is assigned at native receive, before queue admission.
        if kind == 0 { nextInputSequence &+= 1 }
        let inputSequence = kind == 0 ? nextInputSequence : 0
        nextSequence &+= 1
        var record = mmf_trace_record(kind: kind, granularity: granularity, decision: decision, outcome: outcome, reason: reason, sequence: nextSequence, input_sequence: inputSequence, t_ns: tNS - started, extraction_ns: extractionNS, rust_ns: rustNS, apply_ns: applyNS, total_ns: totalNS, horizontal: horizontal, vertical: vertical)
        if mmf_trace_ring_push(ring!, &record) != 0 { available.signal() }
    }

    // Outside the callback: wait for the finite queue to drain so process exit cannot strand a bundle.
    func close() {
        lock.lock()
        guard !closed else { lock.unlock(); return }
        closed = true
        stopping = true
        lock.unlock()
        available.signal()
        _ = drained.wait(timeout: .distantFuture)
    }

    private func take() -> (mmf_trace_record?, UInt64, Bool) {
        var record = mmf_trace_record()
        let popped = mmf_trace_ring_pop(ring!, &record) != 0
        let losses = mmf_trace_ring_take_drops(ring!)
        lock.lock(); totalDropped &+= losses; let shouldStop = stopping && !popped; lock.unlock()
        return (popped ? record : nil, losses, shouldStop)
    }

    private func drain() {
        var index = 1, segmentBytes = 0; var handle: FileHandle?; var sinkFailed = false
        while true {
            _ = available.wait(timeout: .now() + 1)
            while true {
                let (record, losses, shouldStop) = take()
                if record == nil, let reason = takeLifecycle() {
                    let lifecycle = mmf_trace_record(kind: 1, granularity: 0, decision: 0, outcome: 0, reason: reason, sequence: 0, input_sequence: 0, t_ns: DispatchTime.now().uptimeNanoseconds - started, extraction_ns: 0, rust_ns: 0, apply_ns: 0, total_ns: 0, horizontal: 0, vertical: 0)
                    writeLifecycle(lifecycle, &handle, &index, &segmentBytes, &sinkFailed)
                    continue
                }
                if shouldStop {
                    if losses > 0 { writeDrop(losses, &handle, &index, &segmentBytes, &sinkFailed) }
                    try? handle?.close()
                    lock.lock(); let finalDrops = totalDropped; lock.unlock()
                    try? writeManifest(clean: !sinkFailed, drops: finalDrops)
                    TraceStore.shared.lock.lock(); TraceStore.shared.active.remove(destination); TraceStore.shared.lock.unlock()
                    drained.signal(); return
                }
                guard let record else { break }
                if losses > 0 { writeDrop(losses, &handle, &index, &segmentBytes, &sinkFailed) }
                nextPublishSequence &+= 1
                if record.kind == 0 {
                    write(["schema_version": 1, "run_id": runID, "seq": nextPublishSequence, "t_ns": record.t_ns, "level": "trace", "component": "native.input", "name": "input.pipeline", "input_seq": record.input_sequence, "horizontal_lines": record.horizontal, "vertical_lines": record.vertical, "granularity": record.granularity == 1 ? "line_based" : "pixel_based", "decision": decisionName(record.decision), "native_outcome": outcomeName(record.outcome), "reason_code": reasonName(record.reason), "config_revision": NSNull(), "extraction_ns": record.extraction_ns, "rust_eval_ns": record.rust_ns, "native_apply_ns": record.apply_ns, "total_ns": record.total_ns], &handle, &index, &segmentBytes, &sinkFailed)
                } else { writeLifecycle(record, &handle, &index, &segmentBytes, &sinkFailed) }
            }
        }
    }

    private func writeLifecycle(_ record: mmf_trace_record, _ handle: inout FileHandle?, _ index: inout Int, _ bytes: inout Int, _ failed: inout Bool) {
        let name = lifecycleName(record.reason)
        nextPublishSequence &+= 1
        let level = lifecycleLevel(record.reason)
        write(["schema_version": 1, "run_id": runID, "seq": nextPublishSequence, "t_ns": record.t_ns, "level": level, "component": "lifecycle", "name": name], &handle, &index, &bytes, &failed)
        switch level {
        case "error": logger.error("trace \(name, privacy: .public)")
        case "warn": logger.warning("trace \(name, privacy: .public)")
        default: logger.info("trace \(name, privacy: .public)")
        }
    }
    // Publish order is drain serialization order; cross-thread causal order is intentionally not claimed.
    func lifecycle(_ reason: UInt8) {
        lock.lock(); defer { lock.unlock() }
        guard lifecycleCount < lifecycleQueue.count else { totalDropped &+= 1; return }
        lifecycleQueue[lifecycleWrite] = reason; lifecycleWrite = (lifecycleWrite + 1) % lifecycleQueue.count; lifecycleCount += 1; available.signal()
    }
    func callbackLifecycle(_ reason: UInt8) {
        enqueue(horizontal: 0, vertical: 0, granularity: 0, decision: 0, outcome: 0, reason: reason, extractionNS: 0, rustNS: 0, applyNS: 0, totalNS: 0, tNS: DispatchTime.now().uptimeNanoseconds, kind: 1)
    }
    private func takeLifecycle() -> UInt8? {
        lock.lock(); defer { lock.unlock() }
        guard lifecycleCount > 0 else { return nil }
        let reason = lifecycleQueue[lifecycleRead]; lifecycleRead = (lifecycleRead + 1) % lifecycleQueue.count; lifecycleCount -= 1; return reason
    }
    private func writeDrop(_ losses: UInt64, _ handle: inout FileHandle?, _ index: inout Int, _ bytes: inout Int, _ failed: inout Bool) {
        nextPublishSequence &+= 1
        write(["schema_version": 1, "run_id": runID, "seq": nextPublishSequence, "t_ns": DispatchTime.now().uptimeNanoseconds - started, "level": "warn", "component": "observability", "name": "trace.dropped", "drop_count": losses], &handle, &index, &bytes, &failed)
        logger.warning("trace trace.dropped")
    }
    private func write(_ object: [String: Any], _ handle: inout FileHandle?, _ index: inout Int, _ bytes: inout Int, _ failed: inout Bool) {
        guard !failed, let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]) else { failed = true; addLoss(); return }
        TraceStore.shared.lock.lock()
        let reservation = data.count + 1 + traceManifestReserve
        if TraceStore.shared.bytes[root, default: 0] + reservation > traceStoreLimit { pruneOldRuns(reserving: reservation) }
        let admitted = TraceStore.shared.bytes[root, default: 0] + reservation <= traceStoreLimit
        if admitted { TraceStore.shared.bytes[root, default: 0] += data.count + 1 }
        TraceStore.shared.lock.unlock()
        guard admitted else { failed = true; addLoss(); return }
        if handle == nil || bytes + data.count + 1 > traceFileLimit {
            try? handle?.close(); let path = destination.appendingPathComponent("trace-\(index).jsonl")
            FileManager.default.createFile(atPath: path.path, contents: nil); handle = FileHandle(forWritingAtPath: path.path); index += 1; bytes = 0
        }
        guard let handle else { rollbackReservation(data.count + 1); failed = true; addLoss(); return }
        var line = data; line.append(10)
        do { try handle.write(contentsOf: line); bytes += line.count } catch { rollbackReservation(data.count + 1); failed = true; addLoss() }
    }
    private func rollbackReservation(_ bytes: Int) {
        TraceStore.shared.lock.lock(); TraceStore.shared.bytes[root, default: 0] = max(0, TraceStore.shared.bytes[root, default: 0] - bytes); TraceStore.shared.lock.unlock()
    }
    private func addLoss() {
        lock.lock(); totalDropped &+= 1; writerFailed = true; lock.unlock()
        logger.error("trace writer_failed")
    }
    // Init is outside the callback: publish run.start before the drain thread can serialize input.
    private func writeStart() throws {
        nextPublishSequence = 1
        let data = try JSONSerialization.data(withJSONObject: ["schema_version": 1, "run_id": runID, "seq": nextPublishSequence, "t_ns": 0, "level": "info", "component": "lifecycle", "name": "run.start"], options: [.sortedKeys])
        let path = destination.appendingPathComponent("trace-0.jsonl")
        FileManager.default.createFile(atPath: path.path, contents: nil)
        guard let handle = FileHandle(forWritingAtPath: path.path) else { throw NSError(domain: "trace", code: 2) }
        var line = data; line.append(10)
        try handle.write(contentsOf: line)
        try handle.close()
        logger.info("trace run.start")
    }
    private func writeManifest(clean: Bool, drops: UInt64) throws {
        let data = try JSONSerialization.data(withJSONObject: ["schema_version": 1, "run_id": runID, "run_start_utc": runStartUTC, "started_monotonic_ns": started, "clean_shutdown": clean, "drop_count": drops, "writer_failed": writerFailed], options: [.sortedKeys])
        try data.write(to: destination.appendingPathComponent("manifest.json"), options: .atomic)
    }
    private func pruneOldRuns(reserving bytes: Int) {
        let runs = (try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: [.contentModificationDateKey], options: [.skipsHiddenFiles])) ?? []
        for run in runs.filter({ !TraceStore.shared.active.contains($0) && ownsTraceBundle($0) }).sorted(by: { ((try? $0.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast) < ((try? $1.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast) }) where TraceStore.shared.bytes[root, default: 0] + bytes > traceStoreLimit {
            let old = directorySize(run)
            if (try? FileManager.default.removeItem(at: run)) != nil { TraceStore.shared.bytes[root] = max(0, TraceStore.shared.bytes[root, default: 0] - old) }
        }
    }
    private func ownsTraceBundle(_ run: URL) -> Bool {
        let path = run.appendingPathComponent("manifest.json")
        guard (try? path.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true, let data = try? Data(contentsOf: path), let manifest = try? JSONSerialization.jsonObject(with: data) as? [String: Any], integer(manifest["schema_version"]) == 1, manifest["run_id"] as? String == run.lastPathComponent, (integer(manifest["started_monotonic_ns"]) ?? -1) >= 0, boolean(manifest["clean_shutdown"]), (integer(manifest["drop_count"]) ?? -1) >= 0 else { return false }
        let legacy = Set(["schema_version", "run_id", "started_monotonic_ns", "clean_shutdown", "drop_count"])
        let historic = legacy.union(["writer_failed"])
        let current = historic.union(["run_start_utc"])
        guard Set(manifest.keys) == legacy || Set(manifest.keys) == historic && boolean(manifest["writer_failed"]) || Set(manifest.keys) == current && boolean(manifest["writer_failed"]) else { return false }
        return Set(manifest.keys) != current || (manifest["run_start_utc"] as? String).flatMap { $0.hasSuffix("Z") ? ISO8601DateFormatter().date(from: $0) : nil } != nil
    }
    private func boolean(_ value: Any?) -> Bool { guard let value = value as? NSNumber else { return false }; return CFGetTypeID(value) == CFBooleanGetTypeID() }
    private func integer(_ value: Any?) -> Int64? {
        guard let value = value as? NSNumber, CFGetTypeID(value) == CFNumberGetTypeID(), !CFNumberIsFloatType(value) else { return nil }
        var result: Int64 = 0
        return CFNumberGetValue(value, .sInt64Type, &result) ? result : nil
    }
    private func directorySize(_ url: URL) -> Int { guard let entries = FileManager.default.enumerator(at: url, includingPropertiesForKeys: [.fileSizeKey]) else { return 0 }; return entries.reduce(0) { $0 + ((try? ( $1 as? URL)?.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0) } }
}
private func decisionName(_ value: UInt8) -> String { ["preserve", "replace"][Int(value)] }
private func outcomeName(_ value: UInt8) -> String { ["preserved", "applied"][Int(value)] }
private func lifecycleName(_ value: UInt8) -> String { ["run.start", "run.stop", "tap.failure", "source.failure", "tap.timeout", "tap.reenabled", "writer_failed"][Int(value)] }
private func lifecycleLevel(_ value: UInt8) -> String { ["info", "info", "error", "error", "warn", "info", "error"][Int(value)] }
private func reasonName(_ value: UInt8) -> String { ["not_line_based", "preserve", "replace", "engine_unavailable"][Int(value)] }
