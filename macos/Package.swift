// swift-tools-version: 5.10
import PackageDescription

let ffiProfile = Context.environment["MMF_FFI_PROFILE"] ?? "debug"
// "dynamic" links the existing cdylib (default; unchanged prior behavior).
// "static" links the staticlib archive directly so the produced executable has no
// runtime dependency on target/ or the checkout; used only by the local-ship packaging
// path (scripts/local_ship.py) to prove self-containment. Same C ABI either way.
let ffiLinkage = Context.environment["MMF_FFI_LINKAGE"] ?? "dynamic"
let bridgeLinkerSettings: [LinkerSetting] =
    ffiLinkage == "static"
    ? [.unsafeFlags(["../target/\(ffiProfile)/libpointer_input_ffi.a"])]
    : [.unsafeFlags(["-L../target/\(ffiProfile)", "-lpointer_input_ffi"])]

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
            linkerSettings: bridgeLinkerSettings
        ),
        .target(name: "Platform", dependencies: ["Bridge"], path: "Platform/Sources/Platform"),
        .executableTarget(name: "App", dependencies: ["Platform"], path: "App/Sources/App"),
        .executableTarget(name: "CoherenceCheck", dependencies: ["Platform", "Bridge"], path: "Platform/Sources/CoherenceProbe"),
        .executableTarget(name: "Smoke", dependencies: ["Platform"], path: "Platform/Sources/RuntimeSmoke"),
        .executableTarget(name: "Benchmark", dependencies: ["Platform", "Bridge"], path: "Platform/Sources/RuntimeBenchmark"),
        .testTarget(name: "PlatformTests", dependencies: ["Platform"], path: "Platform/Tests/PlatformTests"),
    ],
    swiftLanguageVersions: [.version("6"), .v5]
)
