# Rust FFI ownership

This subtree owns only the narrow C ABI wrapper around the platform-neutral Rust engine.

It may depend on `rust/engine`; the engine must not depend on this subtree. Fixed-layout ABI types and exported functions are introduced only when the C ABI execution slice establishes their contract.
