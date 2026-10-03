import CPointerInput
import Foundation

private let abiVersion: UInt32 = 2
private let successStatus: UInt32 = 0
private let busyStatus: UInt32 = 4
private let systemDirection: UInt32 = 0
private let reverseDirection: UInt32 = 1
private let unknownSource: UInt32 = 2
private let lineBasedGranularity: UInt32 = 0
private let preserveDecision: UInt32 = 0
private let replaceDecision: UInt32 = 1

public enum InputDecision {
    case preserve
    case replace(horizontalHundredths: Int64, verticalHundredths: Int64)
}

public enum ScrollDirection: String, CaseIterable, Codable, Sendable {
    case preserve
    case reverse

    fileprivate var abiValue: UInt32 { self == .preserve ? systemDirection : reverseDirection }
}

public func validate(direction: ScrollDirection, amountPercent: UInt32 = 100) -> Bool {
    var configuration = pointer_input_configuration_v2(
        version: abiVersion,
        size: UInt32(MemoryLayout<pointer_input_configuration_v2>.size),
        direction: direction.abiValue,
        amount_percent: amountPercent,
        reserved: 0
    )
    return pointer_input_configuration_validate_v2(&configuration) == successStatus
}

public final class PointerInputEngine {
    private var owner: UnsafeMutableRawPointer?

    public init?() {
        for _ in 0..<10 {
            let status = pointer_input_engine_create_v2(&owner)
            if status == successStatus, owner != nil { return }
            guard status == busyStatus else { return nil }
            Thread.sleep(forTimeInterval: 0.001)
        }
        return nil
    }

    deinit { _ = pointer_input_engine_destroy_v2(&owner) }

    public func setSystemDirection() -> Bool { setDirection(.preserve) }
    public func setReverseDirection() -> Bool { setDirection(.reverse) }
    public func setDirection(_ direction: ScrollDirection, amountPercent: UInt32 = 100) -> Bool {
        var configuration = pointer_input_configuration_v2(
            version: abiVersion,
            size: UInt32(MemoryLayout<pointer_input_configuration_v2>.size),
            direction: direction.abiValue,
            amount_percent: amountPercent,
            reserved: 0
        )
        return pointer_input_engine_set_configuration_v2(owner, &configuration) == successStatus
    }

    public func evaluate(horizontal: Int64, vertical: Int64) -> InputDecision? {
        var event = pointer_input_event_v2(
            version: abiVersion,
            size: UInt32(MemoryLayout<pointer_input_event_v2>.size),
            source_class: unknownSource,
            granularity: lineBasedGranularity,
            horizontal_lines: horizontal,
            vertical_lines: vertical,
            reserved: (0, 0)
        )
        var output = pointer_input_decision_v2(version: 0, size: 0, decision: 0, reserved: 0, horizontal_hundredths: 0, vertical_hundredths: 0)
        guard pointer_input_engine_evaluate_v2(owner, &event, &output) == successStatus,
              output.version == abiVersion,
              output.size == MemoryLayout<pointer_input_decision_v2>.size,
              output.reserved == 0
        else { return nil }
        switch output.decision {
        case preserveDecision: return .preserve
        case replaceDecision: return .replace(horizontalHundredths: output.horizontal_hundredths, verticalHundredths: output.vertical_hundredths)
        default: return nil
        }
    }

}
