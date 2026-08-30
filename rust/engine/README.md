# Rust engine ownership

This subtree owns platform-neutral Pointer Input domain and engine behavior.

It must not depend on macOS, Swift, AppKit, `CGEvent`, or FFI concerns. Public engine seams are introduced only by the execution slice that establishes their behavior and evidence.
