import AppKit
import SwiftUI
import Platform

@main
struct MacMouseFlowApp: App {
    @StateObject private var runtime = InputRuntime()
    @StateObject private var settingsRequest = SettingsRequest()

    var body: some Scene {
        MenuBarExtra("MacMouseFlow", systemImage: runtime.state == .active ? "scroll" : "scroll.fill") {
            LabeledContent("Status", value: runtime.state.userLabel)
            Divider()
            Toggle("Enable for this session", isOn: Binding(
                get: { runtime.state != .off },
                set: { runtime.setEnabled($0) }
            ))
            if runtime.state == .needsAccessibilityAccess {
                Button("Request Accessibility Access") { runtime.requestAccessibilityAccess() }
            }
            SettingsButton(request: settingsRequest)
            Divider()
            Button("Quit MacMouseFlow") { NSApplication.shared.terminate(nil) }
        }
        .menuBarExtraStyle(.menu)

        Settings {
            SettingsView(runtime: runtime, request: settingsRequest)
        }
        .defaultPosition(.center)
        .defaultSize(width: 760, height: 520)
    }
}

@available(macOS 14.0, *)
private final class SettingsRequest: ObservableObject {
    @Published private(set) var sequence = 0
    func requestPresentation() { sequence &+= 1 }
}

@available(macOS 14.0, *)
private struct SettingsButton: View {
    @ObservedObject var request: SettingsRequest
    @Environment(\.openSettings) private var openSettings

    var body: some View {
        Button("Settings…") {
            request.requestPresentation()
            NSApp.activate()
            openSettings()
        }
    }
}

private struct SettingsView: View {
    @ObservedObject var runtime: InputRuntime
    @ObservedObject var request: SettingsRequest
    @State private var selection: Page

    init(runtime: InputRuntime, request: SettingsRequest) {
        self.runtime = runtime
        self.request = request
        _selection = State(initialValue: AXIsProcessTrusted() ? .scrolling : .access)
    }

    var body: some View {
        NavigationSplitView {
            List(Page.allCases, selection: $selection) { page in
                Label(page.title, systemImage: page.symbol).tag(page)
            }
            .listStyle(.sidebar)
            .navigationSplitViewColumnWidth(min: 180, ideal: 210)
        } detail: {
            VStack(alignment: .leading, spacing: 16) {
                RuntimeStatus(state: runtime.state)
                page
            }
            .padding(24)
            .frame(minWidth: 500, minHeight: 360, alignment: .topLeading)
        }
        .background(SettingsWindowPresenter(request: request))
    }

    @ViewBuilder private var page: some View {
        switch selection {
        case .scrolling: ScrollingPane(runtime: runtime)
        case .access: AccessPane(runtime: runtime)
        case .diagnostics: DiagnosticsPane(runtime: runtime)
        case .about: AboutPane()
        }
    }

    private enum Page: CaseIterable, Identifiable {
        case scrolling, access, diagnostics, about
        var id: Self { self }
        var title: String {
            switch self {
            case .scrolling: "Scrolling"
            case .access: "Access"
            case .diagnostics: "Diagnostics"
            case .about: "About"
            }
        }
        var symbol: String {
            switch self {
            case .scrolling: "scroll"
            case .access: "accessibility"
            case .diagnostics: "stethoscope"
            case .about: "info.circle"
            }
        }
    }
}

private struct RuntimeStatus: View {
    let state: InputRuntimeState

    var body: some View {
        LabeledContent("Current status") {
            Label(state.userLabel, systemImage: state.symbol)
                .foregroundStyle(state == .active ? .green : .secondary)
        }
        .font(.subheadline)
    }
}

private struct ScrollingPane: View {
    @ObservedObject var runtime: InputRuntime

    var body: some View {
        Form {
            Section("Line-Based Scrolling") {
                Toggle("Enable for this session", isOn: Binding(
                    get: { runtime.state != .off },
                    set: { runtime.setEnabled($0) }
                ))
                Text("Turn this on when you want MacMouseFlow to watch for supported scroll input during this session.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            Section("What changes") {
                Text("During this session, the runtime monitors eligible line-based scroll input.")
                Text("Continuous pixel-based scrolling is preserved.")
                Text("MacMouseFlow does not identify individual pointing devices.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .navigationTitle("Scrolling")
    }
}

private struct AccessPane: View {
    @ObservedObject var runtime: InputRuntime

    var body: some View {
        Form {
            Section("Accessibility Access") {
                Text("MacMouseFlow needs Accessibility Access before it can watch supported scroll input.")
                LabeledContent("Access", value: runtime.hasAccessibilityAccess ? "Available" : "Needed")
                if !runtime.hasAccessibilityAccess {
                    Button("Request Accessibility Access") { runtime.requestAccessibilityAccess() }
                } else {
                    Button("Check Access Again") { runtime.refresh() }
                }
            }
            if runtime.state == .inputUnavailable {
                Section("Input") {
                    Text("Changes are not currently being applied. Check access, then try again.")
                    Button("Try Again") { runtime.refresh() }
                }
            }
        }
        .formStyle(.grouped)
        .navigationTitle("Access")
    }
}

private struct DiagnosticsPane: View {
    @ObservedObject var runtime: InputRuntime

    var body: some View {
        Form {
            Section("Runtime") {
                Text("Check whether MacMouseFlow can currently monitor eligible scroll input.")
                LabeledContent("Availability", value: runtime.state.userLabel)
                Button("Check Input Now") { runtime.refresh() }
            }
        }
        .formStyle(.grouped)
        .navigationTitle("Diagnostics")
    }
}

private struct AboutPane: View {
    private let bundle = Bundle.main

    var body: some View {
        Form {
            Section("MacMouseFlow") {
                Text("View the version and build of the app you are using.")
                LabeledContent("Version", value: bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "Development")
                LabeledContent("Build", value: bundle.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "—")
            }
        }
        .formStyle(.grouped)
        .navigationTitle("About")
    }
}

private struct SettingsWindowPresenter: NSViewRepresentable {
    @ObservedObject var request: SettingsRequest

    func makeNSView(context: Context) -> NSView { PresenterView() }
    func updateNSView(_ view: NSView, context: Context) { (view as? PresenterView)?.present(request.sequence) }

    private final class PresenterView: NSView {
        private var pendingSequence = 0
        private var presentedSequence = 0

        required init?(coder: NSCoder) { nil }
        override init(frame frameRect: NSRect) { super.init(frame: frameRect) }

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            presentIfRequested()
        }

        func present(_ sequence: Int) {
            pendingSequence = max(pendingSequence, sequence)
            presentIfRequested()
        }

        private func presentIfRequested() {
            guard pendingSequence > presentedSequence, window != nil else { return }
            let sequence = pendingSequence
            DispatchQueue.main.async {
                guard let window = self.window, self.pendingSequence >= sequence else { return }
                let titlebarPoint = NSPoint(x: window.frame.midX, y: window.frame.maxY - 12)
                if !NSScreen.screens.contains(where: { $0.visibleFrame.contains(titlebarPoint) }),
                   let screen = NSScreen.main ?? NSScreen.screens.first {
                    window.setFrameOrigin(NSPoint(x: screen.visibleFrame.midX - window.frame.width / 2, y: screen.visibleFrame.midY - window.frame.height / 2))
                }
                NSApp.activate()
                window.makeKeyAndOrderFront(nil)
                self.presentedSequence = sequence
            }
        }
    }
}

private extension InputRuntimeState {
    var userLabel: String {
        switch self {
        case .off: "Off"
        case .needsAccessibilityAccess: "Needs Accessibility Access"
        case .active: "Active"
        case .inputUnavailable, .configurationNeedsAttention: "Input Unavailable"
        }
    }

    var symbol: String {
        switch self {
        case .off: "pause.circle"
        case .needsAccessibilityAccess: "lock"
        case .active: "checkmark.circle"
        case .inputUnavailable, .configurationNeedsAttention: "exclamationmark.triangle"
        }
    }
}
