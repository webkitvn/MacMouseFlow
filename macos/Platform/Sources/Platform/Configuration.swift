@_exported import Bridge
import Foundation

public struct PersistedConfiguration: Equatable, Sendable {
    public var enabled: Bool
    public var direction: ScrollDirection
    public var amountPercent: UInt32

    public init(enabled: Bool, direction: ScrollDirection, amountPercent: UInt32 = 100) {
        self.enabled = enabled
        self.direction = direction
        self.amountPercent = amountPercent
    }

    public static let `default` = Self(enabled: false, direction: .preserve)
}

public enum ConfigurationAttention: Equatable {
    case none
    case malformed
    case newerSchema
    case saveFailed
}

public final class ConfigurationStore {
    private struct Document: Codable {
        struct Scroll: Codable {
            let enabled: Bool
            let lineDirection: ScrollDirection
            let lineAmountPercent: UInt32

            enum CodingKeys: String, CodingKey {
                case enabled
                case lineDirection = "line_direction"
                case lineAmountPercent = "line_amount_percent"
            }
        }

        let schemaVersion: Int
        let scroll: Scroll

        enum CodingKeys: String, CodingKey {
            case schemaVersion = "schema_version"
            case scroll
        }
    }

    public let url: URL

    public init(directory: URL? = nil) {
        let base = directory ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("MacMouseFlow", isDirectory: true)
        url = base.appendingPathComponent("configuration.json")
    }

    public func load() -> (PersistedConfiguration, ConfigurationAttention) {
        let data: Data
        do {
            data = try Data(contentsOf: url)
        } catch CocoaError.fileReadNoSuchFile {
            return (.default, .none)
        } catch {
            return (.default, .malformed)
        }
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return (.default, .malformed) }
        let decoded = Self.decode(object)
        guard decoded.1 == .none else { return decoded }
        if Self.schemaVersion(in: object)?.intValue == 1 {
            let result = persistResult(decoded.0)
            guard result == .none else { return (.default, result) }
        }
        return decoded
    }

    private static func decode(_ object: [String: Any]) -> (PersistedConfiguration, ConfigurationAttention) {
        if let attention = Self.newerSchemaAttention(in: object) {
            return (.default, attention)
        }
        guard let version = Self.schemaVersion(in: object) else { return (.default, .malformed) }
        guard version.intValue == 1 || version.intValue == 2,
              Set(object.keys) == ["schema_version", "scroll"],
              let scroll = object["scroll"] as? [String: Any],
              Set(scroll.keys) == (version.intValue == 1 ? ["enabled", "line_direction"] : ["enabled", "line_direction", "line_amount_percent"]),
              let enabled = scroll["enabled"] as? NSNumber,
              CFGetTypeID(enabled) == CFBooleanGetTypeID(),
              let direction = scroll["line_direction"] as? String,
              let lineDirection = ScrollDirection(rawValue: direction) else { return (.default, .malformed) }
        var amountPercent: UInt32 = 100
        if version.intValue == 2 {
            guard let amount = scroll["line_amount_percent"] as? NSNumber,
                  CFGetTypeID(amount) != CFBooleanGetTypeID(),
                  ["c", "s", "i", "l", "q", "C", "S", "I", "L", "Q"].contains(String(cString: amount.objCType)),
                  let value = UInt32(exactly: amount.int64Value) else { return (.default, .malformed) }
            amountPercent = value
        }
        guard validate(direction: lineDirection, amountPercent: amountPercent) else { return (.default, .malformed) }
        let configuration = PersistedConfiguration(enabled: enabled.boolValue, direction: lineDirection, amountPercent: amountPercent)
        return (configuration, .none)
    }

    private static func schemaVersion(in object: [String: Any]) -> NSNumber? {
        guard let version = object["schema_version"] as? NSNumber,
              CFGetTypeID(version) != CFBooleanGetTypeID(),
              ["c", "s", "i", "l", "q", "C", "S", "I", "L", "Q"].contains(String(cString: version.objCType)) else { return nil }
        return version
    }

    private static func newerSchemaAttention(in object: [String: Any]) -> ConfigurationAttention? {
        guard let version = object["schema_version"] as? NSNumber,
              CFGetTypeID(version) != CFBooleanGetTypeID(),
              version.compare(NSNumber(value: 2)) == .orderedDescending || version.decimalValue > Decimal(2) else { return nil }
        // ponytail: preservation is bounded by Foundation decoding/distinct representation (#108); raw-token parsing requires a new contract.
        return .newerSchema
    }

    public func persist(_ configuration: PersistedConfiguration) -> Bool {
        persistResult(configuration) == .none
    }

    func persistResult(_ configuration: PersistedConfiguration, resettingMalformed: Bool = false) -> ConfigurationAttention {
        guard validate(direction: configuration.direction, amountPercent: configuration.amountPercent) else { return .saveFailed }
        let document = Document(schemaVersion: 2, scroll: .init(enabled: configuration.enabled, lineDirection: configuration.direction, lineAmountPercent: configuration.amountPercent))
        guard let data = try? JSONEncoder().encode(document) else { return .saveFailed }
        do {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            let existing: Data?
            do {
                existing = try Data(contentsOf: url)
            } catch CocoaError.fileReadNoSuchFile {
                existing = nil
            }
            if let existing {
                let object = try? JSONSerialization.jsonObject(with: existing) as? [String: Any]
                let attention = object.map { Self.decode($0).1 } ?? .malformed
                guard attention == .none || (resettingMalformed && attention == .malformed) else { return attention }
            }
            try data.write(to: url, options: .atomic)
            return .none
        } catch {
            return .saveFailed
        }
    }
}
