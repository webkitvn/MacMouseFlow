//! Fixed-layout C ABI for the platform-neutral input engine.

use std::{
    any::Any,
    cell::Cell,
    ffi::c_void,
    mem,
    panic::{AssertUnwindSafe, catch_unwind},
    ptr,
    sync::{Condvar, Mutex},
};

use pointer_input_engine as engine;

#[cfg(panic = "abort")]
compile_error!("pointer-input-ffi requires panic = \"unwind\"");

thread_local! {
    static EVALUATING: Cell<bool> = const { Cell::new(false) };
    static INSTALLING_HOOK: Cell<bool> = const { Cell::new(false) };
}

const HOOK_UNINSTALLED: u8 = 0;
const HOOK_INSTALLING: u8 = 1;
const HOOK_INSTALLED: u8 = 2;

static PANIC_HOOK_STATE: Mutex<u8> = Mutex::new(HOOK_UNINSTALLED);
static PANIC_HOOK_STATE_CHANGED: Condvar = Condvar::new();

type PanicPayload = Box<dyn Any + Send + 'static>;

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

struct EvaluationScope(bool);

impl EvaluationScope {
    fn enter() -> Option<Self> {
        EVALUATING
            .try_with(|evaluating| {
                let prior = evaluating.get();
                evaluating.set(true);
                Self(prior)
            })
            .ok()
    }
}

impl Drop for EvaluationScope {
    fn drop(&mut self) {
        let _ = EVALUATING.try_with(|evaluating| evaluating.set(self.0));
    }
}

fn discard_panic_payload(payload: PanicPayload) {
    if let Err(secondary_payload) = catch_unwind(AssertUnwindSafe(|| drop(payload))) {
        mem::forget(secondary_payload);
    }
}

fn panic_status(payload: PanicPayload) -> PointerInputStatusV1 {
    discard_panic_payload(payload);
    PointerInputStatusV1::Panic
}

fn finish_hook_installation(state: u8) {
    let mut current = PANIC_HOOK_STATE
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    *current = state;
    PANIC_HOOK_STATE_CHANGED.notify_all();
}

fn install_panic_hook() -> Result<(), ()> {
    let mut state = PANIC_HOOK_STATE
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    loop {
        match *state {
            HOOK_INSTALLED => return Ok(()),
            HOOK_UNINSTALLED => {
                *state = HOOK_INSTALLING;
                break;
            }
            HOOK_INSTALLING if INSTALLING_HOOK.try_with(Cell::get).unwrap_or(false) => {
                return Err(());
            }
            HOOK_INSTALLING => {
                state = PANIC_HOOK_STATE_CHANGED
                    .wait(state)
                    .unwrap_or_else(|poisoned| poisoned.into_inner());
            }
            _ => return Err(()),
        }
    }
    drop(state);

    let result = INSTALLING_HOOK.try_with(|installing| {
        installing.set(true);
        let result = catch_unwind(AssertUnwindSafe(|| {
            #[cfg(test)]
            if PANIC_HOOK_INSTALL_FAILURE.swap(false, std::sync::atomic::Ordering::Relaxed) {
                panic!("test-only hook installation failure");
            }
            #[cfg(test)]
            {
                let gate = INSTALLATION_GATE
                    .lock()
                    .unwrap_or_else(|poisoned| poisoned.into_inner())
                    .take();
                if let Some(gate) = gate {
                    gate.wait();
                }
            }
            let previous_hook = std::panic::take_hook();
            std::panic::set_hook(Box::new(move |info| {
                if !EVALUATING.try_with(Cell::get).unwrap_or(false) {
                    previous_hook(info);
                }
            }));
        }));
        installing.set(false);
        result
    });

    match result {
        Ok(Ok(())) => {
            finish_hook_installation(HOOK_INSTALLED);
            Ok(())
        }
        Ok(Err(payload)) => {
            finish_hook_installation(HOOK_UNINSTALLED);
            discard_panic_payload(payload);
            Err(())
        }
        Err(_) => {
            finish_hook_installation(HOOK_UNINSTALLED);
            Err(())
        }
    }
}

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
/// `out_engine` must point to writable, initially null storage for one owner handle.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn pointer_input_engine_create_v1(
    out_engine: *mut *mut c_void,
) -> PointerInputStatusV1 {
    if out_engine.is_null() {
        return PointerInputStatusV1::InvalidArgument;
    }
    // SAFETY: validated pointer to caller-owned handle storage.
    if !unsafe { out_engine.read() }.is_null() {
        return PointerInputStatusV1::InvalidArgument;
    }

    match catch_unwind(AssertUnwindSafe(|| {
        install_panic_hook()?;
        let engine = Box::new(engine::Engine::new(engine::ScrollConfiguration::system()));
        // SAFETY: validated non-null caller storage.
        unsafe { out_engine.write(Box::into_raw(engine).cast()) };
        Ok::<_, ()>(PointerInputStatusV1::Success)
    })) {
        Ok(Ok(status)) => status,
        Ok(Err(())) => PointerInputStatusV1::Panic,
        Err(payload) => panic_status(payload),
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
        Err(payload) => panic_status(payload),
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

    let Some(_scope) = EvaluationScope::enter() else {
        return PointerInputStatusV1::Panic;
    };
    match catch_unwind(AssertUnwindSafe(|| {
        // SAFETY: validated non-null pointer to a caller-owned POD value.
        let Some(event) = event_from(unsafe { event.read() }) else {
            return PointerInputStatusV1::InvalidArgument;
        };
        maybe_inject_evaluation_panic();
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
        Err(payload) => panic_status(payload),
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
        Err(payload) => panic_status(payload),
    }
}

#[cfg(test)]
static PANIC_ON_EVALUATE: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
#[cfg(test)]
static PANIC_ON_DROP: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
#[cfg(test)]
static PANIC_HOOK_INSTALL_FAILURE: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);
#[cfg(test)]
static INSTALLATION_GATE: Mutex<Option<std::sync::Arc<std::sync::Barrier>>> = Mutex::new(None);

#[cfg(test)]
struct PanicOnDrop;

#[cfg(test)]
impl Drop for PanicOnDrop {
    fn drop(&mut self) {
        panic!("test-only panic payload drop");
    }
}

#[cfg(test)]
fn maybe_inject_evaluation_panic() {
    use std::sync::atomic::Ordering;

    if PANIC_ON_DROP.swap(false, Ordering::Relaxed) {
        std::panic::panic_any(PanicOnDrop);
    }
    if PANIC_ON_EVALUATE.swap(false, Ordering::Relaxed) {
        panic!("test-only evaluation panic");
    }
}

#[cfg(not(test))]
fn maybe_inject_evaluation_panic() {}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        panic::{AssertUnwindSafe, catch_unwind},
        sync::{
            Arc, Barrier, Mutex,
            atomic::{AtomicBool, AtomicUsize, Ordering},
        },
    };

    fn event() -> PointerInputEventV1 {
        PointerInputEventV1 {
            version: POINTER_INPUT_ABI_VERSION_V1,
            size: size_of::<PointerInputEventV1>() as u32,
            source_class: POINTER_INPUT_SOURCE_UNKNOWN_V1,
            granularity: POINTER_INPUT_GRANULARITY_LINE_BASED_V1,
            horizontal_lines: 0,
            vertical_lines: 3,
            reserved: [0; 2],
        }
    }

    #[test]
    fn panic_policy_is_fail_open_and_delegates_only_unmarked_panics() {
        // ponytail: this sole hook-touching unit test retains the wrapper until process exit.
        let _previous_hook = std::panic::take_hook();
        let delegated = Arc::new(AtomicUsize::new(0));
        let trigger_reentrant_create = Arc::new(AtomicBool::new(true));
        let reentrant_result = Arc::new(Mutex::new(None));
        let counter = Arc::clone(&delegated);
        let reenter = Arc::clone(&trigger_reentrant_create);
        let reentrant_result_for_hook = Arc::clone(&reentrant_result);
        std::panic::set_hook(Box::new(move |_| {
            counter.fetch_add(1, Ordering::Relaxed);
            if reenter.swap(false, Ordering::Relaxed) {
                let mut owner = ptr::null_mut();
                let status = unsafe { pointer_input_engine_create_v1(&raw mut owner) };
                *reentrant_result_for_hook
                    .lock()
                    .unwrap_or_else(|poisoned| poisoned.into_inner()) =
                    Some((status, owner.is_null()));
            }
        }));
        *INSTALLATION_GATE
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner()) = None;

        let result = catch_unwind(AssertUnwindSafe(|| {
            let event = event();
            let mut output = preserve_output();
            let mut failed_owner = ptr::null_mut();

            PANIC_HOOK_INSTALL_FAILURE.store(true, Ordering::Relaxed);
            let failed_startup = unsafe { pointer_input_engine_create_v1(&raw mut failed_owner) };
            let reentrant_startup = *reentrant_result
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());

            let install_gate = Arc::new(Barrier::new(2));
            *INSTALLATION_GATE
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner()) = Some(Arc::clone(&install_gate));
            let starter = std::thread::spawn(move || {
                let mut owner = ptr::null_mut();
                let status = unsafe { pointer_input_engine_create_v1(&raw mut owner) };
                (status, owner as usize)
            });
            install_gate.wait();
            let mut concurrent_owner = ptr::null_mut();
            let concurrent_status =
                unsafe { pointer_input_engine_create_v1(&raw mut concurrent_owner) };
            let (startup_status, startup_owner) =
                starter.join().expect("installing creator must not panic");
            let mut startup_owner = startup_owner as *mut c_void;
            let delegated_before_unrelated = delegated.load(Ordering::Relaxed);
            let _ = catch_unwind(|| panic!("unrelated test panic"));
            let delegated_after_unrelated = delegated.load(Ordering::Relaxed);

            assert_eq!(failed_startup, PointerInputStatusV1::Panic);
            assert!(failed_owner.is_null());
            assert_eq!(reentrant_startup, Some((PointerInputStatusV1::Panic, true)));
            assert_eq!(startup_status, PointerInputStatusV1::Success);
            assert_eq!(concurrent_status, PointerInputStatusV1::Success);
            assert_eq!(delegated_after_unrelated, delegated_before_unrelated + 1);

            // ponytail: test-only latch, remove if a real internal fault path gains public-seam coverage.
            PANIC_ON_EVALUATE.store(true, Ordering::Relaxed);
            let delegated_before_evaluation = delegated.load(Ordering::Relaxed);
            let first_panic_status = unsafe {
                pointer_input_engine_evaluate_v1(
                    concurrent_owner,
                    &raw const event,
                    &raw mut output,
                )
            };
            let first_panic_decision = output.decision;
            let delegated_after_evaluation = delegated.load(Ordering::Relaxed);

            PANIC_ON_DROP.store(true, Ordering::Relaxed);
            let delegated_before_payload_drop = delegated.load(Ordering::Relaxed);
            let drop_panic_status = unsafe {
                pointer_input_engine_evaluate_v1(
                    concurrent_owner,
                    &raw const event,
                    &raw mut output,
                )
            };
            let drop_panic_decision = output.decision;
            let delegated_after_payload_drop = delegated.load(Ordering::Relaxed);
            let concurrent_destroy_status =
                unsafe { pointer_input_engine_destroy_v1(&raw mut concurrent_owner) };
            let startup_destroy_status =
                unsafe { pointer_input_engine_destroy_v1(&raw mut startup_owner) };

            let mut post_destroy_owner = ptr::null_mut();
            let post_destroy_status =
                unsafe { pointer_input_engine_create_v1(&raw mut post_destroy_owner) };
            let post_destroy_evaluation = unsafe {
                pointer_input_engine_evaluate_v1(
                    post_destroy_owner,
                    &raw const event,
                    &raw mut output,
                )
            };
            let post_destroy_cleanup =
                unsafe { pointer_input_engine_destroy_v1(&raw mut post_destroy_owner) };

            assert_eq!(first_panic_status, PointerInputStatusV1::Panic);
            assert_eq!(first_panic_decision, POINTER_INPUT_DECISION_PRESERVE_V1);
            assert_eq!(delegated_after_evaluation, delegated_before_evaluation);
            assert_eq!(drop_panic_status, PointerInputStatusV1::Panic);
            assert_eq!(drop_panic_decision, POINTER_INPUT_DECISION_PRESERVE_V1);
            assert_eq!(delegated_after_payload_drop, delegated_before_payload_drop);
            assert_eq!(concurrent_destroy_status, PointerInputStatusV1::Success);
            assert_eq!(startup_destroy_status, PointerInputStatusV1::Success);
            assert_eq!(post_destroy_status, PointerInputStatusV1::Success);
            assert_eq!(post_destroy_evaluation, PointerInputStatusV1::Success);
            assert_eq!(post_destroy_cleanup, PointerInputStatusV1::Success);
        }));

        PANIC_ON_EVALUATE.store(false, Ordering::Relaxed);
        PANIC_ON_DROP.store(false, Ordering::Relaxed);
        PANIC_HOOK_INSTALL_FAILURE.store(false, Ordering::Relaxed);
        *INSTALLATION_GATE
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner()) = None;
        if let Err(payload) = result {
            std::panic::resume_unwind(payload);
        }
    }
}
