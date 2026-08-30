# macOS Platform ownership

This subtree owns macOS lifecycle and system boundaries: Accessibility, input capture/application, persistence I/O, and observability sinks.

The input callback must remain bounded and fail open according to the canonical architecture decisions. Concrete platform APIs are introduced only by the slice that owns them.
