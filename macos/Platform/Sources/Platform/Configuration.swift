@_exported import Bridge
import Foundation

public struct PersistedConfiguration: Equatable, Sendable {
    public var enabled: Bool
    public var direction: ScrollDirection

    public init(enabled: Bool, direction: ScrollDirection) {
        self.enabled = enabled
        self.direction = direction
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

            enum CodingKeys: String, CodingKey {
                case enabled
                case lineDirection = "line_direction"
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
        guard let data = try? Data(contentsOf: url) else { return (.default, .none) }
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let version = object["schema_version"] as? NSNumber,
              CFGetTypeID(version) != CFBooleanGetTypeID() else { return (.default, .malformed) }
        let type = String(cString: version.objCType)
        guard ["c", "s", "i", "l", "q", "C", "S", "I", "L", "Q"].contains(type) else { return (.default, .malformed) }
        guard version.intValue <= 1 else { return (.default, .newerSchema) }
        guard version.intValue == 1,
              Set(object.keys) == ["schema_version", "scroll"],
              let scroll = object["scroll"] as? [String: Any],
              Set(scroll.keys) == ["enabled", "line_direction"],
              let enabled = scroll["enabled"] as? NSNumber,
              CFGetTypeID(enabled) == CFBooleanGetTypeID(),
              let direction = scroll["line_direction"] as? String,
              let lineDirection = ScrollDirection(rawValue: direction),
              validate(direction: lineDirection) else { return (.default, .malformed) }
        return (PersistedConfiguration(enabled: enabled.boolValue, direction: lineDirection), .none)
    }

    public func persist(_ configuration: PersistedConfiguration) -> Bool {
        guard validate(direction: configuration.direction) else { return false }
        let document = Document(schemaVersion: 1, scroll: .init(enabled: configuration.enabled, lineDirection: configuration.direction))
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
