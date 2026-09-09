// swift-tools-version: 6.0
import PackageDescription

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
            linkerSettings: [.unsafeFlags(["-L../target/debug", "-lpointer_input_ffi"])]
        ),
        .target(name: "Platform", dependencies: ["Bridge"], path: "Platform/Sources/Platform"),
        .executableTarget(name: "App", dependencies: ["Platform"], path: "App/Sources/App"),
        .executableTarget(name: "CoherenceCheck", dependencies: ["Platform", "Bridge"], path: "Platform/Sources/CoherenceProbe"),
        .executableTarget(name: "Smoke", dependencies: ["Platform"], path: "Platform/Sources/RuntimeSmoke"),
        .executableTarget(name: "Benchmark", dependencies: ["Platform", "Bridge"], path: "Platform/Sources/RuntimeBenchmark"),
        .testTarget(name: "PlatformTests", dependencies: ["Platform"], path: "Platform/Tests/PlatformTests"),
    ]
)
