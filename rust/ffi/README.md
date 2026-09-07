# Rust FFI ownership

This subtree owns only the narrow C ABI wrapper around the platform-neutral Rust engine.

It may depend on `rust/engine`; the engine must not depend on this subtree.

## Handle lifetime

Create requires an initially null owner variable; a non-null owner is rejected unchanged. The handle variable returned by create is the sole owner and may destroy the allocation. A copied non-owning handle value may call configuration update or evaluation concurrently while the owner keeps the allocation live. The owner must wait for those calls to finish before destroy; concurrent destroy, use after destruction, and stale or fabricated values violate the C contract.
