//! Fixed-layout C ABI for the platform-neutral input engine.

use std::{
    ffi::c_void,
    panic::{AssertUnwindSafe, catch_unwind},
    ptr,
};

use pointer_input_engine as engine;

/// The fixed-layout ABI version implemented by this library.
pub const POINTER_INPUT_ABI_VERSION_V1: u32 = 1;
/// Preserve the input event.
pub const POINTER_INPUT_DECISION_PRESERVE_V1: u32 = 0;
/// Replace the input event with the returned line deltas.
pub const POINTER_INPUT_DECISION_REPLACE_V1: u32 = 1;
/// Preserve the system direction.
pub const POINTER_INPUT_DIRECTION_SYSTEM_V1: u32 = 0;
/// Reverse eligible line-based input.
pub const POINTER_INPUT_DIRECTION_REVERSE_V1: u32 = 1;
/// Source class: mouse.
pub const POINTER_INPUT_SOURCE_MOUSE_V1: u32 = 0;
/// Source class: trackpad.
pub const POINTER_INPUT_SOURCE_TRACKPAD_V1: u32 = 1;
/// Source class: unavailable.
pub const POINTER_INPUT_SOURCE_UNKNOWN_V1: u32 = 2;
/// Discrete line-based input.
pub const POINTER_INPUT_GRANULARITY_LINE_BASED_V1: u32 = 0;
/// Continuous pixel-based input.
pub const POINTER_INPUT_GRANULARITY_PIXEL_BASED_V1: u32 = 1;

/// Status returned by each ABI operation.
#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PointerInputStatusV1 {
    /// The operation completed.
    Success = 0,
    /// A required pointer, layout, or value was invalid.
    InvalidArgument = 1,
    /// Evaluation could not safely produce a replacement.
    EvaluationFailed = 2,
    /// A Rust panic was caught before it could cross the ABI boundary.
    Panic = 3,
}

/// C input event. `version` and `size` must exactly match this layout; `reserved` must be zero.
#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct PointerInputEventV1 {
    /// ABI version.
    pub version: u32,
    /// Exact `sizeof(PointerInputEventV1)`.
    pub size: u32,
    /// One of the `POINTER_INPUT_SOURCE_*_V1` constants.
    pub source_class: u32,
    /// One of the `POINTER_INPUT_GRANULARITY_*_V1` constants.
    pub granularity: u32,
    /// Horizontal line delta.
    pub horizontal_lines: i64,
    /// Vertical line delta.
    pub vertical_lines: i64,
    /// Reserved for a future ABI version; must contain zeroes.
    pub reserved: [u32; 2],
}

/// C configuration. `version` and `size` must exactly match this layout; `reserved` must be zero.
#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct PointerInputConfigurationV1 {
    /// ABI version.
    pub version: u32,
    /// Exact `sizeof(PointerInputConfigurationV1)`.
    pub size: u32,
    /// One of the `POINTER_INPUT_DIRECTION_*_V1` constants.
    pub direction: u32,
    /// Reserved for a future ABI version; must contain zero.
    pub reserved: u32,
}

/// C evaluation output. The ABI initializes a non-null output to Preserve before validation.
#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct PointerInputDecisionV1 {
    /// ABI version.
    pub version: u32,
    /// Exact `sizeof(PointerInputDecisionV1)`.
    pub size: u32,
    /// One of the `POINTER_INPUT_DECISION_*_V1` constants.
    pub decision: u32,
    /// Reserved for a future ABI version; always zero in output.
    pub reserved: u32,
    /// Replacement horizontal line delta when `decision` is Replace.
    pub horizontal_lines: i64,
    /// Replacement vertical line delta when `decision` is Replace.
    pub vertical_lines: i64,
}

#[cfg(test)]
static PANIC_ON_EVALUATE: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

fn preserve_output() -> PointerInputDecisionV1 {
    PointerInputDecisionV1 {
        version: POINTER_INPUT_ABI_VERSION_V1,
        size: size_of::<PointerInputDecisionV1>() as u32,
        decision: POINTER_INPUT_DECISION_PRESERVE_V1,
        reserved: 0,
        horizontal_lines: 0,
        vertical_lines: 0,
    }
}

fn valid_layout(version: u32, size: u32, expected_size: usize) -> bool {
    version == POINTER_INPUT_ABI_VERSION_V1 && size == expected_size as u32
}

fn configuration_from(value: PointerInputConfigurationV1) -> Option<engine::ScrollConfiguration> {
    if !valid_layout(
        value.version,
        value.size,
        size_of::<PointerInputConfigurationV1>(),
    ) || value.reserved != 0
    {
        return None;
    }

    match value.direction {
        POINTER_INPUT_DIRECTION_SYSTEM_V1 => Some(engine::ScrollConfiguration::system()),
        POINTER_INPUT_DIRECTION_REVERSE_V1 => Some(engine::ScrollConfiguration::reverse()),
        _ => None,
    }
}

fn event_from(value: PointerInputEventV1) -> Option<engine::InputEvent> {
    if !valid_layout(value.version, value.size, size_of::<PointerInputEventV1>())
        || value.reserved != [0; 2]
    {
        return None;
    }

    let source_class = match value.source_class {
        POINTER_INPUT_SOURCE_MOUSE_V1 => engine::SourceClass::Mouse,
        POINTER_INPUT_SOURCE_TRACKPAD_V1 => engine::SourceClass::Trackpad,
        POINTER_INPUT_SOURCE_UNKNOWN_V1 => engine::SourceClass::Unknown,
        _ => return None,
    };
    let granularity = match value.granularity {
        POINTER_INPUT_GRANULARITY_LINE_BASED_V1 => engine::ScrollGranularity::LineBased,
        POINTER_INPUT_GRANULARITY_PIXEL_BASED_V1 => engine::ScrollGranularity::PixelBased,
        _ => return None,
    };

    Some(engine::InputEvent::Scroll(engine::ScrollEvent {
        source: engine::InputSource { source_class },
        granularity,
        horizontal_lines: value.horizontal_lines,
        vertical_lines: value.vertical_lines,
    }))
}

unsafe fn engine_from<'a>(handle: *mut c_void) -> &'a engine::Engine {
    // SAFETY: callers guarantee the allocation remains live for this call.
    unsafe { &*handle.cast::<engine::Engine>() }
}

/// Allocates an opaque engine with system direction.
///
/// # Safety
/// `out_engine` must point to writable storage for one handle.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn pointer_input_engine_create_v1(
    out_engine: *mut *mut c_void,
) -> PointerInputStatusV1 {
    if out_engine.is_null() {
        return PointerInputStatusV1::InvalidArgument;
    }

    match catch_unwind(AssertUnwindSafe(|| {
        let engine = Box::new(engine::Engine::new(engine::ScrollConfiguration::system()));
        // SAFETY: validated non-null caller storage.
        unsafe { out_engine.write(Box::into_raw(engine).cast()) };
        PointerInputStatusV1::Success
    })) {
        Ok(status) => status,
        Err(_) => PointerInputStatusV1::Panic,
    }
}

/// Replaces the configuration observed by later evaluations.
///
/// # Safety
/// `handle` must refer to a live allocation returned by create and `configuration` must point to
/// its fixed-layout value. A copied non-owning handle may call this concurrently with evaluation
/// while the owner keeps the allocation live. Stale, fabricated, use-after-destroy, and
/// concurrently destroyed handles violate the caller contract.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn pointer_input_engine_set_configuration_v1(
    handle: *mut c_void,
    configuration: *const PointerInputConfigurationV1,
) -> PointerInputStatusV1 {
    if handle.is_null() || configuration.is_null() {
        return PointerInputStatusV1::InvalidArgument;
    }

    match catch_unwind(AssertUnwindSafe(|| {
        // SAFETY: validated non-null pointer to a caller-owned POD value.
        let Some(configuration) = configuration_from(unsafe { configuration.read() }) else {
            return PointerInputStatusV1::InvalidArgument;
        };
        // SAFETY: documented caller ownership contract for `handle`.
        unsafe { engine_from(handle) }.set_configuration(configuration);
        PointerInputStatusV1::Success
    })) {
        Ok(status) => status,
        Err(_) => PointerInputStatusV1::Panic,
    }
}

/// Evaluates one normalized event and writes a fail-open decision.
///
/// # Safety
/// `handle` must refer to a live allocation returned by create. `event` and `out_decision` must
/// point to readable and writable fixed-layout values respectively. A copied non-owning handle may
/// call this concurrently with configuration updates while the owner keeps the allocation live.
/// Stale, fabricated, use-after-destroy, and concurrently destroyed handles violate the caller
/// contract.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn pointer_input_engine_evaluate_v1(
    handle: *mut c_void,
    event: *const PointerInputEventV1,
    out_decision: *mut PointerInputDecisionV1,
) -> PointerInputStatusV1 {
    if out_decision.is_null() {
        return PointerInputStatusV1::InvalidArgument;
    }

    // SAFETY: validated non-null caller output storage; write the fail-open value before input use.
    unsafe { out_decision.write(preserve_output()) };
    if handle.is_null() || event.is_null() {
        return PointerInputStatusV1::InvalidArgument;
    }

    match catch_unwind(AssertUnwindSafe(|| {
        // SAFETY: validated non-null pointer to a caller-owned POD value.
        let Some(event) = event_from(unsafe { event.read() }) else {
            return PointerInputStatusV1::InvalidArgument;
        };
        #[cfg(test)]
        if PANIC_ON_EVALUATE.swap(false, std::sync::atomic::Ordering::Relaxed) {
            panic!("test-only evaluation panic");
        }
        // SAFETY: documented caller ownership contract for `handle`.
        let evaluation = unsafe { engine_from(handle) }.evaluate(event);
        match evaluation.status {
            engine::EvaluationStatus::Success => {
                let output = match evaluation.decision {
                    engine::InputDecision::Preserve => preserve_output(),
                    engine::InputDecision::Replace(scroll) => PointerInputDecisionV1 {
                        decision: POINTER_INPUT_DECISION_REPLACE_V1,
                        horizontal_lines: scroll.horizontal_lines,
                        vertical_lines: scroll.vertical_lines,
                        ..preserve_output()
                    },
                };
                // SAFETY: output was validated and initialized before evaluation.
                unsafe { out_decision.write(output) };
                PointerInputStatusV1::Success
            }
            engine::EvaluationStatus::EvaluationFailed => PointerInputStatusV1::EvaluationFailed,
        }
    })) {
        Ok(status) => status,
        Err(_) => PointerInputStatusV1::Panic,
    }
}

/// Nulls and releases an opaque engine handle.
///
/// # Safety
/// `in_out_handle` must point to the owner's unique live handle variable, or to a null owner
/// variable for idempotent cleanup. The owner must keep the allocation live until all non-owning
/// copied handle uses finish. Concurrent destruction, use-after-destroy, stale, and fabricated
/// values violate the caller contract.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn pointer_input_engine_destroy_v1(
    in_out_handle: *mut *mut c_void,
) -> PointerInputStatusV1 {
    if in_out_handle.is_null() {
        return PointerInputStatusV1::InvalidArgument;
    }

    match catch_unwind(AssertUnwindSafe(|| {
        // SAFETY: validated pointer to caller-owned handle storage.
        let handle = unsafe { in_out_handle.read() };
        if handle.is_null() {
            return PointerInputStatusV1::Success;
        }
        // SAFETY: null the caller variable before releasing the owned allocation.
        unsafe { in_out_handle.write(ptr::null_mut()) };
        // SAFETY: documented caller ownership contract guarantees an allocation from create.
        drop(unsafe { Box::from_raw(handle.cast::<engine::Engine>()) });
        PointerInputStatusV1::Success
    })) {
        Ok(status) => status,
        Err(_) => PointerInputStatusV1::Panic,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::Ordering;

    #[test]
    fn evaluation_panic_returns_status_and_preserves_output() {
        let mut handle = ptr::null_mut();
        let event = PointerInputEventV1 {
            version: POINTER_INPUT_ABI_VERSION_V1,
            size: size_of::<PointerInputEventV1>() as u32,
            source_class: POINTER_INPUT_SOURCE_UNKNOWN_V1,
            granularity: POINTER_INPUT_GRANULARITY_LINE_BASED_V1,
            horizontal_lines: 0,
            vertical_lines: 3,
            reserved: [0; 2],
        };
        let mut output = preserve_output();

        // ponytail: test-only latch, remove if a real internal fault path gains public-seam coverage.
        PANIC_ON_EVALUATE.store(true, Ordering::Relaxed);
        assert_eq!(
            unsafe { pointer_input_engine_create_v1(&raw mut handle) },
            PointerInputStatusV1::Success
        );
        assert_eq!(
            unsafe { pointer_input_engine_evaluate_v1(handle, &raw const event, &raw mut output) },
            PointerInputStatusV1::Panic
        );
        assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V1);
        assert_eq!(
            unsafe { pointer_input_engine_destroy_v1(&raw mut handle) },
            PointerInputStatusV1::Success
        );
    }
}
