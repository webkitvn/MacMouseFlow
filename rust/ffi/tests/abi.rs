use pointer_input_ffi::{
    POINTER_INPUT_ABI_VERSION_V1, POINTER_INPUT_DECISION_PRESERVE_V1,
    POINTER_INPUT_DECISION_REPLACE_V1, POINTER_INPUT_DIRECTION_REVERSE_V1,
    POINTER_INPUT_GRANULARITY_LINE_BASED_V1, POINTER_INPUT_GRANULARITY_PIXEL_BASED_V1,
    POINTER_INPUT_SOURCE_UNKNOWN_V1, PointerInputConfigurationV1, PointerInputDecisionV1,
    PointerInputEventV1, PointerInputStatusV1, pointer_input_engine_create_v1,
    pointer_input_engine_destroy_v1, pointer_input_engine_evaluate_v1,
    pointer_input_engine_set_configuration_v1,
};

fn event(granularity: u32, horizontal_lines: i64, vertical_lines: i64) -> PointerInputEventV1 {
    PointerInputEventV1 {
        version: POINTER_INPUT_ABI_VERSION_V1,
        size: size_of::<PointerInputEventV1>() as u32,
        source_class: POINTER_INPUT_SOURCE_UNKNOWN_V1,
        granularity,
        horizontal_lines,
        vertical_lines,
        reserved: [0; 2],
    }
}

fn decision() -> PointerInputDecisionV1 {
    PointerInputDecisionV1 {
        version: 0,
        size: 0,
        decision: u32::MAX,
        reserved: 1,
        horizontal_lines: 99,
        vertical_lines: 99,
    }
}

fn create(engine: &mut *mut core::ffi::c_void) -> PointerInputStatusV1 {
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(1);
    loop {
        let status = unsafe { pointer_input_engine_create_v1(engine) };
        if status != PointerInputStatusV1::Busy
            || !engine.is_null()
            || std::time::Instant::now() >= deadline
        {
            return status;
        }
        std::thread::yield_now();
    }
}

#[test]
fn rejects_non_exact_event_layout_with_initialized_preserve_output() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let mut input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V1, 0, 3);
    input.size -= 1;

    assert_eq!(create(&mut engine), PointerInputStatusV1::Success);
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v1(engine, &raw const input, &raw mut output) },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V1);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
}

#[test]
fn rejects_incompatible_version_and_reserved_fields() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let mut input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V1, 0, 3);

    assert_eq!(create(&mut engine), PointerInputStatusV1::Success);
    input.version += 1;
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v1(engine, &raw const input, &raw mut output) },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V1);
    input.version = POINTER_INPUT_ABI_VERSION_V1;
    input.reserved[1] = 1;
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v1(engine, &raw const input, &raw mut output) },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V1);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
}

#[test]
fn rejects_invalid_event_tags_with_initialized_preserve_output() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let mut input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V1, 0, 3);

    assert_eq!(create(&mut engine), PointerInputStatusV1::Success);
    input.source_class = u32::MAX;
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v1(engine, &raw const input, &raw mut output) },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V1);
    input.source_class = POINTER_INPUT_SOURCE_UNKNOWN_V1;
    input.granularity = u32::MAX;
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v1(engine, &raw const input, &raw mut output) },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V1);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
}

#[test]
fn invalid_configuration_leaves_active_direction_unchanged() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let configuration = PointerInputConfigurationV1 {
        version: POINTER_INPUT_ABI_VERSION_V1,
        size: size_of::<PointerInputConfigurationV1>() as u32,
        direction: POINTER_INPUT_DIRECTION_REVERSE_V1,
        reserved: 0,
    };
    let input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V1, 0, 3);

    assert_eq!(create(&mut engine), PointerInputStatusV1::Success);
    assert_eq!(
        unsafe { pointer_input_engine_set_configuration_v1(engine, &raw const configuration) },
        PointerInputStatusV1::Success
    );
    for invalid_configuration in [
        PointerInputConfigurationV1 {
            version: POINTER_INPUT_ABI_VERSION_V1 + 1,
            ..configuration
        },
        PointerInputConfigurationV1 {
            size: configuration.size - 1,
            ..configuration
        },
        PointerInputConfigurationV1 {
            reserved: 1,
            ..configuration
        },
        PointerInputConfigurationV1 {
            direction: u32::MAX,
            ..configuration
        },
    ] {
        assert_eq!(
            unsafe {
                pointer_input_engine_set_configuration_v1(engine, &raw const invalid_configuration)
            },
            PointerInputStatusV1::InvalidArgument
        );
        assert_eq!(
            unsafe { pointer_input_engine_evaluate_v1(engine, &raw const input, &raw mut output) },
            PointerInputStatusV1::Success
        );
        assert_eq!(output.decision, POINTER_INPUT_DECISION_REPLACE_V1);
        assert_eq!(output.vertical_lines, -3);
    }
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
}

#[test]
fn pixel_input_preserves_under_reverse_configuration() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let configuration = PointerInputConfigurationV1 {
        version: POINTER_INPUT_ABI_VERSION_V1,
        size: size_of::<PointerInputConfigurationV1>() as u32,
        direction: POINTER_INPUT_DIRECTION_REVERSE_V1,
        reserved: 0,
    };
    let input = event(POINTER_INPUT_GRANULARITY_PIXEL_BASED_V1, 2, -3);

    assert_eq!(create(&mut engine), PointerInputStatusV1::Success);
    assert_eq!(
        unsafe { pointer_input_engine_set_configuration_v1(engine, &raw const configuration) },
        PointerInputStatusV1::Success
    );
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v1(engine, &raw const input, &raw mut output) },
        PointerInputStatusV1::Success
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V1);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
}

#[test]
fn rejects_null_abi_inputs_and_preserves_evaluation_output() {
    let mut engine = core::ptr::null_mut();
    let configuration = PointerInputConfigurationV1 {
        version: POINTER_INPUT_ABI_VERSION_V1,
        size: size_of::<PointerInputConfigurationV1>() as u32,
        direction: POINTER_INPUT_DIRECTION_REVERSE_V1,
        reserved: 0,
    };
    let input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V1, 0, 3);
    let mut output = decision();

    assert_eq!(
        unsafe { pointer_input_engine_create_v1(core::ptr::null_mut()) },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(create(&mut engine), PointerInputStatusV1::Success);
    assert_eq!(
        unsafe { pointer_input_engine_set_configuration_v1(engine, core::ptr::null()) },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(
        unsafe {
            pointer_input_engine_set_configuration_v1(
                core::ptr::null_mut(),
                &raw const configuration,
            )
        },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v1(engine, core::ptr::null(), &raw mut output) },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V1);
    output = decision();
    assert_eq!(
        unsafe {
            pointer_input_engine_evaluate_v1(
                core::ptr::null_mut(),
                &raw const input,
                &raw mut output,
            )
        },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V1);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(core::ptr::null_mut()) },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
}

#[test]
fn rejects_null_output_without_dereferencing_it() {
    let mut engine = core::ptr::null_mut();
    let input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V1, 0, 3);

    assert_eq!(create(&mut engine), PointerInputStatusV1::Success);
    assert_eq!(
        unsafe {
            pointer_input_engine_evaluate_v1(engine, &raw const input, core::ptr::null_mut())
        },
        PointerInputStatusV1::InvalidArgument
    );
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
}

#[test]
fn overflow_returns_failure_and_preserve() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let configuration = PointerInputConfigurationV1 {
        version: POINTER_INPUT_ABI_VERSION_V1,
        size: size_of::<PointerInputConfigurationV1>() as u32,
        direction: POINTER_INPUT_DIRECTION_REVERSE_V1,
        reserved: 0,
    };
    let input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V1, i64::MIN, 1);

    assert_eq!(create(&mut engine), PointerInputStatusV1::Success);
    assert_eq!(
        unsafe { pointer_input_engine_set_configuration_v1(engine, &raw const configuration) },
        PointerInputStatusV1::Success
    );
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v1(engine, &raw const input, &raw mut output) },
        PointerInputStatusV1::EvaluationFailed
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V1);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
}

#[test]
fn create_rejects_live_owner_without_overwriting_it() {
    let mut engine = core::ptr::null_mut();

    assert_eq!(create(&mut engine), PointerInputStatusV1::Success);
    let owner = engine;
    assert_eq!(create(&mut engine), PointerInputStatusV1::InvalidArgument);
    assert_eq!(engine, owner);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
}

#[test]
fn destroy_nulls_owning_variable_and_repeat_is_safe() {
    let mut engine = core::ptr::null_mut();

    assert_eq!(create(&mut engine), PointerInputStatusV1::Success);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
    assert!(engine.is_null());
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v1(&raw mut engine) },
        PointerInputStatusV1::Success
    );
}
