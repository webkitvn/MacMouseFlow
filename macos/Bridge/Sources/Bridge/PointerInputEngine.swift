import CPointerInput

private let abiVersion: UInt32 = 1
private let successStatus: UInt32 = 0
private let systemDirection: UInt32 = 0
private let reverseDirection: UInt32 = 1
private let unknownSource: UInt32 = 2
private let lineBasedGranularity: UInt32 = 0
private let preserveDecision: UInt32 = 0
private let replaceDecision: UInt32 = 1

public enum InputDecision {
    case preserve
    case replace(horizontal: Int64, vertical: Int64)
}

public final class PointerInputEngine {
    private var owner: UnsafeMutableRawPointer?

    public init?() {
        guard pointer_input_engine_create_v1(&owner) == successStatus, owner != nil else { return nil }
    }

    deinit { _ = pointer_input_engine_destroy_v1(&owner) }

    public func setSystemDirection() -> Bool { setDirection(systemDirection) }
    public func setReverseDirection() -> Bool { setDirection(reverseDirection) }

    public func evaluate(horizontal: Int64, vertical: Int64) -> InputDecision? {
        var event = pointer_input_event_v1(
            version: abiVersion,
            size: UInt32(MemoryLayout<pointer_input_event_v1>.size),
            source_class: unknownSource,
            granularity: lineBasedGranularity,
            horizontal_lines: horizontal,
            vertical_lines: vertical,
            reserved: (0, 0)
        )
        var output = pointer_input_decision_v1(version: 0, size: 0, decision: 0, reserved: 0, horizontal_lines: 0, vertical_lines: 0)
        guard pointer_input_engine_evaluate_v1(owner, &event, &output) == successStatus,
              output.version == abiVersion,
              output.size == MemoryLayout<pointer_input_decision_v1>.size,
              output.reserved == 0
        else { return nil }
        switch output.decision {
        case preserveDecision: return .preserve
        case replaceDecision: return .replace(horizontal: output.horizontal_lines, vertical: output.vertical_lines)
        default: return nil
        }
    }

    private func setDirection(_ direction: UInt32) -> Bool {
        var configuration = pointer_input_configuration_v1(
            version: abiVersion,
            size: UInt32(MemoryLayout<pointer_input_configuration_v1>.size),
            direction: direction,
            reserved: 0
        )
        return pointer_input_engine_set_configuration_v1(owner, &configuration) == successStatus
    }
}
