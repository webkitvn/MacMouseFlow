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
            Toggle("Enable", isOn: Binding(
                get: { runtime.configuration.enabled },
                set: { runtime.setEnabled($0) }
            ))
            .disabled(!runtime.canEditConfiguration)
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
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            runtime.refresh()
        }
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

// Track distance represents equal ratios: 25, 50, 100, 200, 400.
enum ScrollAmountScale {
    static func position(for percent: UInt32) -> Double {
        log2(Double(percent) / 100)
    }

    static func percent(at position: Double) -> UInt32 {
        UInt32((100 * exp2(min(2, max(-2, position)))).rounded())
    }
}

private struct ScrollingPane: View {
    @ObservedObject var runtime: InputRuntime
    @State private var pendingAmount: UInt32?
    @State private var isEditingAmount = false
    @State private var amountSaved = false

    var body: some View {
        Form {
            Section("Line-Based Scrolling") {
                Toggle("Enable", isOn: Binding(
                    get: { runtime.configuration.enabled },
                    set: { runtime.setEnabled($0) }
                ))
                .disabled(!runtime.canEditConfiguration)
                Picker("Line direction", selection: Binding(
                    get: { runtime.configuration.direction },
                    set: { runtime.setDirection($0) }
                )) {
                    Text("Preserve").tag(ScrollDirection.preserve)
                    Text("Reverse").tag(ScrollDirection.reverse)
                }
                .disabled(!runtime.canEditConfiguration)
                VStack(alignment: .leading) {
                    HStack {
                        Text("Scroll Amount")
                        Spacer()
                        Text("\(runtime.configuration.amountPercent)%")
                            .monospacedDigit()
                    }
                    Slider(value: Binding(
                        get: { ScrollAmountScale.position(for: pendingAmount ?? runtime.configuration.amountPercent) },
                        set: { stageAmount(ScrollAmountScale.percent(at: $0)) }
                    ), in: -2...2, onEditingChanged: { editing in
                        isEditingAmount = editing
                        if !editing && NSApp.currentEvent?.type == .leftMouseUp { commitPendingAmount() }
                    }) {
                        Text("Scroll Amount")
                    }
                    .labelsHidden()
                    .accessibilityValue(pendingAmount.map { "\($0) percent, not saved. Unchanged amount: \(runtime.configuration.amountPercent) percent" } ?? "\(runtime.configuration.amountPercent) percent")
                    .disabled(!runtime.canEditConfiguration)
                    Text("Lower amounts move less for the same line-based input; higher amounts move more. At 100%, the amount is unchanged.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    if let pendingAmount {
                        Text("\(pendingAmount)% — not saved yet. Unchanged amount: \(runtime.configuration.amountPercent)%.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else if amountSaved && runtime.configurationAttention == .none {
                        Text("Scroll Amount saved.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                    if (pendingAmount ?? runtime.configuration.amountPercent) != 100 {
                        Button("Reset to 100%") { stageAmount(100) }
                            .disabled(!runtime.canEditConfiguration || isEditingAmount)
                    }
                }
                if runtime.configurationAttention == .malformed {
                    Text("Your configuration could not be read. Changes are disabled until you reset it.")
                    Button("Reset Configuration") { runtime.resetMalformedConfiguration() }
                } else if runtime.configurationAttention == .newerSchema {
                    Text("This configuration was created by a newer version. It is read-only and has not been changed.")
                } else if runtime.migrationFailed {
                    Text("Your saved settings could not be updated. Scrolling changes are off and your saved settings are unchanged. Quit and reopen MacMouseFlow to try again.")
                } else if runtime.configurationAttention == .saveFailed {
                    Text("Your changes could not be saved. Your previous settings are still in use.")
                }
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
        .task(id: isEditingAmount ? nil : pendingAmount) {
            guard !isEditingAmount, pendingAmount != nil else { return }
            do {
                // Batch keyboard adjustments; dragging waits for the native editing-end callback.
                try await Task.sleep(for: .milliseconds(250))
            } catch { return }
            guard !Task.isCancelled else { return }
            commitPendingAmount()
        }
        .onDisappear {
            isEditingAmount = false
            commitPendingAmount()
        }
    }

    private func commitPendingAmount() {
        guard let amount = pendingAmount else { return }
        pendingAmount = nil
        let previousAmount = runtime.configuration.amountPercent
        runtime.setAmountPercent(amount)
        amountSaved = previousAmount != amount && runtime.configuration.amountPercent == amount && runtime.configurationAttention == .none
    }

    private func stageAmount(_ amount: UInt32) {
        amountSaved = false
        pendingAmount = amount == runtime.configuration.amountPercent ? nil : amount
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
        case .inputUnavailable: "Input Unavailable"
        case .configurationNeedsAttention: "Configuration Needs Attention"
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
