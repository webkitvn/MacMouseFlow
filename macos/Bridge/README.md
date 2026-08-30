# macOS Bridge ownership

This subtree owns the Swift-facing wrapper around the narrow C ABI.

It must not own `CGEventTap`, persistence, UI, or domain policy. Concrete bridge types are introduced only after the Rust/C ABI seam is established by its execution slice.
