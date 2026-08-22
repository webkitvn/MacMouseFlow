# Keep configuration persistence native and explicitly versioned

For v0.1, the native Swift layer owns the app-specific Application Support location, JSON decoding/encoding, and atomic replacement of a single versioned configuration document, while Rust owns `Scroll Configuration` semantics and validation. Persisted data is a storage DTO (đối tượng truyền dữ liệu lưu trữ), not the domain model: startup and UI updates decode outside the input callback, pass a candidate configuration through the Rust validation/update boundary, and only activate a validated snapshot. Missing, corrupt, or unsupported-newer data fails safe to preserve/no-op behavior; a newer unsupported document is left untouched so an older rollback build cannot silently downgrade or destroy it.

## Considered Options

- `UserDefaults` keys as the canonical store: rejected for v0.1 because the schema would be implicit and scattered, making migration, rollback behavior, inspection, and AI-assisted diagnosis less explicit than one versioned document.
- Rust-owned filesystem and serialization: rejected because app-support location and storage lifecycle are platform concerns, and moving byte-buffer/file ownership across the native/Rust boundary would expand the integration surface without improving hot-path semantics.

## Consequences

The v0.1 document contains only the global/default-scope state required for line-based scroll direction and feature enablement; it must not persist `Device Identity` or `Device Profile`. Writes happen off the input hot path and use atomic replace semantics. Known older versions may migrate only through an explicit migration path whose result is validated by Rust before replacement; unknown newer versions are never overwritten automatically. The file format is internal and versioned, not a public compatibility API.