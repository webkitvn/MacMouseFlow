// swift-tools-version: 5.10
import PackageDescription

let ffiProfile = Context.environment["MMF_FFI_PROFILE"] ?? "debug"
#if compiler(>=6.0)
let preferredSwiftSettings: [SwiftSetting] = [.unsafeFlags(["-swift-version", "6"])]
#else
let preferredSwiftSettings: [SwiftSetting] = []
#endif

let package = Package(
    name: "MacMouseFlow",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "macmouseflow", targets: ["App"]),
        .executable(name: "coherence-check", targets: ["CoherenceCheck"]),
        .executable(name: "smoke", targets: ["Smoke"]),
        .executable(name: "benchmark", targets: ["Benchmark"]),
    ],
    targets: [
        .systemLibrary(name: "CPointerInput", path: "Bridge/CPointerInput"),
        .target(
            name: "Bridge",
            dependencies: ["CPointerInput"],
            path: "Bridge/Sources/Bridge",
            swiftSettings: preferredSwiftSettings,
            linkerSettings: [.unsafeFlags(["-L../target/\(ffiProfile)", "-lpointer_input_ffi"])]
        ),
        .target(name: "Platform", dependencies: ["Bridge"], path: "Platform/Sources/Platform", swiftSettings: preferredSwiftSettings),
        .executableTarget(name: "App", dependencies: ["Platform"], path: "App/Sources/App", swiftSettings: preferredSwiftSettings),
        .executableTarget(name: "CoherenceCheck", dependencies: ["Platform", "Bridge"], path: "Platform/Sources/CoherenceProbe", swiftSettings: preferredSwiftSettings),
        .executableTarget(name: "Smoke", dependencies: ["Platform"], path: "Platform/Sources/RuntimeSmoke", swiftSettings: preferredSwiftSettings),
        .executableTarget(name: "Benchmark", dependencies: ["Platform", "Bridge"], path: "Platform/Sources/RuntimeBenchmark", swiftSettings: preferredSwiftSettings),
        .testTarget(name: "PlatformTests", dependencies: ["Platform"], path: "Platform/Tests/PlatformTests", swiftSettings: preferredSwiftSettings),
    ]
)
