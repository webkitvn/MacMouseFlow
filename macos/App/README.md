# macOS App ownership

This subtree owns SwiftUI/AppKit composition and user-visible runtime state.

It must not call raw FFI or own `CGEventTap` directly. Product UI and runtime behavior are introduced only by execution slices with established seams and acceptance evidence.
