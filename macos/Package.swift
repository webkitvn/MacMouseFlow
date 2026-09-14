// swift-tools-version: 5.10
import PackageDescription

let ffiProfile = Context.environment["MMF_FFI_PROFILE"] ?? "debug"
// "dynamic" links the existing cdylib (default; unchanged prior behavior).
// "static" links the staticlib archive directly so the produced executable has no
// runtime dependency on target/ or the checkout; used only by the local-ship packaging
// path (scripts/local_ship.py) to prove self-containment. Same C ABI either way.
let ffiLinkage = Context.environment["MMF_FFI_LINKAGE"] ?? "dynamic"
// Set only by the local-ship packaging path (scripts/local_ship.py), which builds the
// Rust FFI crate with an explicit `--target aarch64-apple-darwin` (ADR-0006: macOS 14+
// on Apple Silicon only through v1) rather than the host's default target triple. Cargo
// then places its output under `target/<triple>/<profile>/` instead of
// `target/<profile>/`. Unset for every other build path (dev builds, smoke, benchmark,
// coherence-check), which keeps their prior unqualified `target/<profile>/` behavior.
let ffiTargetTriple = Context.environment["MMF_FFI_TARGET_TRIPLE"]
let ffiTargetDir = ffiTargetTriple.map { "\($0)/\(ffiProfile)" } ?? ffiProfile
let bridgeLinkerSettings: [LinkerSetting] =
    ffiLinkage == "static"
    ? [.unsafeFlags(["../target/\(ffiTargetDir)/libpointer_input_ffi.a"])]
    : [.unsafeFlags(["-L../target/\(ffiTargetDir)", "-lpointer_input_ffi"])]

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
