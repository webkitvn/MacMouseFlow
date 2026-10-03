use pointer_input_ffi::{
    POINTER_INPUT_ABI_VERSION_V2, POINTER_INPUT_DECISION_PRESERVE_V2,
    POINTER_INPUT_DECISION_REPLACE_V2, POINTER_INPUT_DIRECTION_REVERSE_V2,
    POINTER_INPUT_GRANULARITY_LINE_BASED_V2, POINTER_INPUT_GRANULARITY_PIXEL_BASED_V2,
    POINTER_INPUT_SOURCE_UNKNOWN_V2, PointerInputConfigurationV2, PointerInputDecisionV2,
    PointerInputEventV2, PointerInputStatusV2, pointer_input_configuration_validate_v2,
    pointer_input_engine_create_v2, pointer_input_engine_destroy_v2,
    pointer_input_engine_evaluate_v2, pointer_input_engine_set_configuration_v2,
};

fn event(granularity: u32, horizontal_lines: i64, vertical_lines: i64) -> PointerInputEventV2 {
    PointerInputEventV2 {
        version: POINTER_INPUT_ABI_VERSION_V2,
        size: size_of::<PointerInputEventV2>() as u32,
        source_class: POINTER_INPUT_SOURCE_UNKNOWN_V2,
        granularity,
        horizontal_lines,
        vertical_lines,
        reserved: [0; 2],
    }
}

fn decision() -> PointerInputDecisionV2 {
    PointerInputDecisionV2 {
        version: 0,
        size: 0,
        decision: u32::MAX,
        reserved: 1,
        horizontal_hundredths: 99,
        vertical_hundredths: 99,
    }
}

fn create(engine: &mut *mut core::ffi::c_void) -> PointerInputStatusV2 {
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(1);
    loop {
        let status = unsafe { pointer_input_engine_create_v2(engine) };
        if status != PointerInputStatusV2::Busy
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
    let mut input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V2, 0, 3);
    input.size -= 1;

    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v2(engine, &raw const input, &raw mut output) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V2);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn rejects_incompatible_version_and_reserved_fields() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let mut input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V2, 0, 3);

    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    input.version += 1;
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v2(engine, &raw const input, &raw mut output) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V2);
    input.version = POINTER_INPUT_ABI_VERSION_V2;
    input.reserved[1] = 1;
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v2(engine, &raw const input, &raw mut output) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V2);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn rejects_invalid_event_tags_with_initialized_preserve_output() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let mut input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V2, 0, 3);

    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    input.source_class = u32::MAX;
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v2(engine, &raw const input, &raw mut output) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V2);
    input.source_class = POINTER_INPUT_SOURCE_UNKNOWN_V2;
    input.granularity = u32::MAX;
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v2(engine, &raw const input, &raw mut output) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V2);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn validation_accepts_valid_configuration_and_rejects_null_or_invalid_layout_without_mutation() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let configuration = PointerInputConfigurationV2 {
        version: POINTER_INPUT_ABI_VERSION_V2,
        size: size_of::<PointerInputConfigurationV2>() as u32,
        direction: POINTER_INPUT_DIRECTION_REVERSE_V2,
        amount_percent: 100,
        reserved: 0,
    };
    let invalid = PointerInputConfigurationV2 {
        reserved: 1,
        ..configuration
    };
    let input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V2, 0, 3);

    assert_eq!(
        unsafe { pointer_input_configuration_validate_v2(&raw const configuration) },
        PointerInputStatusV2::Success
    );
    assert_eq!(
        unsafe { pointer_input_configuration_validate_v2(&raw const invalid) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(
        unsafe { pointer_input_configuration_validate_v2(core::ptr::null()) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v2(engine, &raw const input, &raw mut output) },
        PointerInputStatusV2::Success
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V2);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn invalid_configuration_leaves_active_direction_unchanged() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let configuration = PointerInputConfigurationV2 {
        version: POINTER_INPUT_ABI_VERSION_V2,
        size: size_of::<PointerInputConfigurationV2>() as u32,
        direction: POINTER_INPUT_DIRECTION_REVERSE_V2,
        amount_percent: 100,
        reserved: 0,
    };
    let input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V2, 0, 3);

    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    assert_eq!(
        unsafe { pointer_input_engine_set_configuration_v2(engine, &raw const configuration) },
        PointerInputStatusV2::Success
    );
    for invalid_configuration in [
        PointerInputConfigurationV2 {
            amount_percent: 24,
            ..configuration
        },
        PointerInputConfigurationV2 {
            amount_percent: 401,
            ..configuration
        },
        PointerInputConfigurationV2 {
            version: POINTER_INPUT_ABI_VERSION_V2 + 1,
            ..configuration
        },
        PointerInputConfigurationV2 {
            size: configuration.size - 1,
            ..configuration
        },
        PointerInputConfigurationV2 {
            reserved: 1,
            ..configuration
        },
        PointerInputConfigurationV2 {
            direction: u32::MAX,
            ..configuration
        },
    ] {
        assert_eq!(
            unsafe {
                pointer_input_engine_set_configuration_v2(engine, &raw const invalid_configuration)
            },
            PointerInputStatusV2::InvalidArgument
        );
        assert_eq!(
            unsafe { pointer_input_engine_evaluate_v2(engine, &raw const input, &raw mut output) },
            PointerInputStatusV2::Success
        );
        assert_eq!(output.decision, POINTER_INPUT_DECISION_REPLACE_V2);
        assert_eq!(output.vertical_hundredths, -300);
    }
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn pixel_input_preserves_under_reverse_configuration() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let configuration = PointerInputConfigurationV2 {
        version: POINTER_INPUT_ABI_VERSION_V2,
        size: size_of::<PointerInputConfigurationV2>() as u32,
        direction: POINTER_INPUT_DIRECTION_REVERSE_V2,
        amount_percent: 100,
        reserved: 0,
    };
    let input = event(POINTER_INPUT_GRANULARITY_PIXEL_BASED_V2, 2, -3);

    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    assert_eq!(
        unsafe { pointer_input_engine_set_configuration_v2(engine, &raw const configuration) },
        PointerInputStatusV2::Success
    );
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v2(engine, &raw const input, &raw mut output) },
        PointerInputStatusV2::Success
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V2);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn rejects_null_abi_inputs_and_preserves_evaluation_output() {
    let mut engine = core::ptr::null_mut();
    let configuration = PointerInputConfigurationV2 {
        version: POINTER_INPUT_ABI_VERSION_V2,
        size: size_of::<PointerInputConfigurationV2>() as u32,
        direction: POINTER_INPUT_DIRECTION_REVERSE_V2,
        amount_percent: 100,
        reserved: 0,
    };
    let input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V2, 0, 3);
    let mut output = decision();

    assert_eq!(
        unsafe { pointer_input_engine_create_v2(core::ptr::null_mut()) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    assert_eq!(
        unsafe { pointer_input_engine_set_configuration_v2(engine, core::ptr::null()) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(
        unsafe {
            pointer_input_engine_set_configuration_v2(
                core::ptr::null_mut(),
                &raw const configuration,
            )
        },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v2(engine, core::ptr::null(), &raw mut output) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V2);
    output = decision();
    assert_eq!(
        unsafe {
            pointer_input_engine_evaluate_v2(
                core::ptr::null_mut(),
                &raw const input,
                &raw mut output,
            )
        },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V2);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(core::ptr::null_mut()) },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn rejects_null_output_without_dereferencing_it() {
    let mut engine = core::ptr::null_mut();
    let input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V2, 0, 3);

    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    assert_eq!(
        unsafe {
            pointer_input_engine_evaluate_v2(engine, &raw const input, core::ptr::null_mut())
        },
        PointerInputStatusV2::InvalidArgument
    );
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn overflow_returns_failure_and_preserve() {
    let mut engine = core::ptr::null_mut();
    let mut output = decision();
    let configuration = PointerInputConfigurationV2 {
        version: POINTER_INPUT_ABI_VERSION_V2,
        size: size_of::<PointerInputConfigurationV2>() as u32,
        direction: POINTER_INPUT_DIRECTION_REVERSE_V2,
        amount_percent: 100,
        reserved: 0,
    };
    let input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V2, i64::MIN, 1);

    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    assert_eq!(
        unsafe { pointer_input_engine_set_configuration_v2(engine, &raw const configuration) },
        PointerInputStatusV2::Success
    );
    assert_eq!(
        unsafe { pointer_input_engine_evaluate_v2(engine, &raw const input, &raw mut output) },
        PointerInputStatusV2::EvaluationFailed
    );
    assert_eq!(output.decision, POINTER_INPUT_DECISION_PRESERVE_V2);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn create_rejects_live_owner_without_overwriting_it() {
    let mut engine = core::ptr::null_mut();

    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    let owner = engine;
    assert_eq!(create(&mut engine), PointerInputStatusV2::InvalidArgument);
    assert_eq!(engine, owner);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn destroy_nulls_owning_variable_and_repeat_is_safe() {
    let mut engine = core::ptr::null_mut();

    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
    assert!(engine.is_null());
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&raw mut engine) },
        PointerInputStatusV2::Success
    );
}

#[test]
fn v2_carries_exact_hundredths_for_both_directions() {
    let mut engine = core::ptr::null_mut();
    assert_eq!(create(&mut engine), PointerInputStatusV2::Success);
    for (direction, amount_percent, expected) in [
        (0, 25, 25),
        (0, 50, 50),
        (0, 137, 137),
        (1, 100, -100),
        (1, 50, -50),
    ] {
        let configuration = PointerInputConfigurationV2 {
            version: POINTER_INPUT_ABI_VERSION_V2,
            size: size_of::<PointerInputConfigurationV2>() as u32,
            direction,
            amount_percent,
            reserved: 0,
        };
        let input = event(POINTER_INPUT_GRANULARITY_LINE_BASED_V2, 1, -1);
        let mut output = decision();
        assert_eq!(
            unsafe { pointer_input_engine_set_configuration_v2(engine, &configuration) },
            PointerInputStatusV2::Success
        );
        assert_eq!(
            unsafe { pointer_input_engine_evaluate_v2(engine, &input, &mut output) },
            PointerInputStatusV2::Success
        );
        assert_eq!(output.horizontal_hundredths, expected);
        assert_eq!(output.vertical_hundredths, -expected);
        assert_eq!(output.version, 2);
        assert_eq!(output.size, 32);
        assert_eq!(output.reserved, 0);
    }
    assert_eq!(
        unsafe { pointer_input_engine_destroy_v2(&mut engine) },
        PointerInputStatusV2::Success
    );
}
