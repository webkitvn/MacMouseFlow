import SwiftUI
import Platform

@main
struct MacMouseFlowApp: App {
    @StateObject private var runtime = InputRuntime()

    var body: some Scene {
        MenuBarExtra("MacMouseFlow", systemImage: menuIcon) {
            Text(statusText)
            Divider()
            Toggle("Enable scrolling", isOn: Binding(
                get: { runtime.state != .off },
                set: { runtime.setEnabled($0) }
            ))
            if runtime.state == .needsAccessibilityAccess {
                Button("Allow Accessibility Access") { runtime.requestAccessibilityAccess() }
            }
            SettingsLink()
            Divider()
            Button("Quit MacMouseFlow") { NSApplication.shared.terminate(nil) }
        }
        .menuBarExtraStyle(.menu)

        Settings {
            SettingsView(runtime: runtime)
                .frame(minWidth: 640, minHeight: 420)
        }
    }

    private var statusText: String { runtime.state.label }
    private var menuIcon: String { runtime.state == .active ? "scroll" : "scroll.fill" }
}

private struct SettingsView: View {
    @ObservedObject var runtime: InputRuntime
    @State private var selection = Page.scrolling

    var body: some View {
        NavigationSplitView {
            List(Page.allCases, selection: $selection) { page in
                Label(page.title, systemImage: page.symbol)
                    .tag(page)
            }
            .listStyle(.sidebar)
        } detail: {
            Form {
                Text(selection.title).font(.title2)
                switch selection {
                case .scrolling:
                    Toggle("Enable scrolling", isOn: Binding(
                        get: { runtime.state != .off },
                        set: { runtime.setEnabled($0) }
                    ))
                    Text("LineBased scrolling is available when enabled. PixelBased scroll is preserved.")
                case .access:
                    Text(runtime.state.label)
                    Button("Allow Accessibility Access") { runtime.requestAccessibilityAccess() }
                case .diagnostics:
                    Text(runtime.state.label)
                    Text("Configuration Needs Attention is unavailable until configuration persistence is implemented.")
                    Button("Check input now") { runtime.refresh() }
                case .about:
                    Text("MacMouseFlow")
                    Text("A native utility for line-based scrolling.")
                }
            }
            .padding()
        }
    }

    private enum Page: String, CaseIterable, Identifiable {
        case scrolling, access, diagnostics, about
        var id: Self { self }
        var title: String { rawValue.capitalized }
        var symbol: String {
            switch self {
            case .scrolling: "scroll"
            case .access: "lock"
            case .diagnostics: "stethoscope"
            case .about: "info.circle"
            }
        }
    }
}

private extension InputRuntimeState {
    var label: String {
        switch self {
        case .off: "Off"
        case .needsAccessibilityAccess: "Needs Accessibility Access"
        case .active: "Active"
        case .inputUnavailable: "Input Unavailable"
        case .configurationNeedsAttention: "Configuration Needs Attention"
        }
    }
}
