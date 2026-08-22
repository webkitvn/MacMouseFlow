# Domain model planning summary

The canonical domain language is defined in `CONTEXT.md`. This note records only planning consequences for the current release horizon.

- Platform-specific input is normalized before entering the domain.
- The domain begins at `Input Event` plus `Input Source`.
- A source may be class-only or unknown; reliable device identity is optional.
- Scroll transformation produces an `Input Decision`, not an `Action`.
- `Binding`, `Action`, and `Device Profile` remain canonical concepts for later capabilities and do not gate the first scrolling release.
