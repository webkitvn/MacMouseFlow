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
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let version = object["schema_version"] as? NSNumber,
              CFGetTypeID(version) != CFBooleanGetTypeID() else { return (.default, .malformed) }
        let type = String(cString: version.objCType)
        guard ["c", "s", "i", "l", "q", "C", "S", "I", "L", "Q"].contains(type) else { return (.default, .malformed) }
        guard version.compare(NSNumber(value: 2)) != .orderedDescending else { return (.default, .newerSchema) }
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
        if version.intValue == 1, !persist(configuration) { return (.default, .saveFailed) }
        return (configuration, .none)
    }

    public func persist(_ configuration: PersistedConfiguration) -> Bool {
        guard validate(direction: configuration.direction, amountPercent: configuration.amountPercent) else { return false }
        let document = Document(schemaVersion: 2, scroll: .init(enabled: configuration.enabled, lineDirection: configuration.direction, lineAmountPercent: configuration.amountPercent))
        guard let data = try? JSONEncoder().encode(document) else { return false }
        do {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try data.write(to: url, options: .atomic)
            return true
        } catch {
            return false
        }
    }
}
