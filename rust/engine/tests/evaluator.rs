use pointer_input_engine::{
    EvaluationStatus, InputDecision, InputEvent, InputSource, ScrollConfiguration, ScrollEvent,
    ScrollGranularity, SourceClass,
};

fn line_event(horizontal_lines: i64, vertical_lines: i64, source_class: SourceClass) -> InputEvent {
    InputEvent::Scroll(ScrollEvent {
        source: InputSource { source_class },
        granularity: ScrollGranularity::LineBased,
        horizontal_lines,
        vertical_lines,
    })
}

#[test]
fn reverse_accepts_unknown_source_without_changing_behavior() {
    let engine = pointer_input_engine::Engine::new(ScrollConfiguration::reverse());

    let unknown = engine.evaluate(line_event(0, 3, SourceClass::Unknown));
    let mouse = engine.evaluate(line_event(0, 3, SourceClass::Mouse));

    assert_eq!(unknown.status, mouse.status);
    assert_eq!(
        unknown.decision,
        InputDecision::Replace(ScrollEvent {
            source: InputSource {
                source_class: SourceClass::Unknown,
            },
            granularity: ScrollGranularity::LineBased,
            horizontal_lines: 0,
            vertical_lines: -3,
        })
    );
    assert_eq!(
        mouse.decision,
        InputDecision::Replace(ScrollEvent {
            source: InputSource {
                source_class: SourceClass::Mouse,
            },
            granularity: ScrollGranularity::LineBased,
            horizontal_lines: 0,
            vertical_lines: -3,
        })
    );
}

#[test]
fn system_direction_preserves_line_scroll() {
    let engine = pointer_input_engine::Engine::new(ScrollConfiguration::system());

    let result = engine.evaluate(line_event(2, -3, SourceClass::Trackpad));

    assert_eq!(
        result,
        pointer_input_engine::Evaluation::success(InputDecision::Preserve)
    );
}

#[test]
fn reverse_replaces_one_axis_line_scroll() {
    let engine = pointer_input_engine::Engine::new(ScrollConfiguration::reverse());

    let result = engine.evaluate(line_event(0, 3, SourceClass::Unknown));

    assert_eq!(
        result,
        pointer_input_engine::Evaluation::success(InputDecision::Replace(ScrollEvent {
            source: InputSource {
                source_class: SourceClass::Unknown,
            },
            granularity: ScrollGranularity::LineBased,
            horizontal_lines: 0,
            vertical_lines: -3,
        }))
    );
}

#[test]
fn reverse_preserves_both_zero_line_scroll() {
    let engine = pointer_input_engine::Engine::new(ScrollConfiguration::reverse());

    let result = engine.evaluate(line_event(0, 0, SourceClass::Unknown));

    assert_eq!(
        result,
        pointer_input_engine::Evaluation::success(InputDecision::Preserve)
    );
}

#[test]
fn reverse_overflow_fails_open() {
    let engine = pointer_input_engine::Engine::new(ScrollConfiguration::reverse());

    let result = engine.evaluate(line_event(i64::MIN, 1, SourceClass::Unknown));

    assert_eq!(result.status, EvaluationStatus::EvaluationFailed);
    assert_eq!(result.decision, InputDecision::Preserve);
}

#[test]
fn reverse_negates_literal_two_axis_line_scroll_cases() {
    let engine = pointer_input_engine::Engine::new(ScrollConfiguration::reverse());

    for (horizontal_lines, vertical_lines, expected_horizontal, expected_vertical) in
        [(17, 3, -17, -3), (-17, -3, 17, 3), (17, -3, -17, 3)]
    {
        let result = engine.evaluate(line_event(
            horizontal_lines,
            vertical_lines,
            SourceClass::Unknown,
        ));

        assert_eq!(result.status, EvaluationStatus::Success);
        assert_eq!(
            result.decision,
            InputDecision::Replace(ScrollEvent {
                source: InputSource {
                    source_class: SourceClass::Unknown,
                },
                granularity: ScrollGranularity::LineBased,
                horizontal_lines: expected_horizontal,
                vertical_lines: expected_vertical,
            })
        );
    }
}

#[test]
fn pixel_scroll_preserves_under_reverse_configuration() {
    let engine = pointer_input_engine::Engine::new(ScrollConfiguration::reverse());
    let event = InputEvent::Scroll(ScrollEvent {
        source: InputSource {
            source_class: SourceClass::Unknown,
        },
        granularity: ScrollGranularity::PixelBased,
        horizontal_lines: 4,
        vertical_lines: -7,
    });

    let result = engine.evaluate(event);

    assert_eq!(
        result,
        pointer_input_engine::Evaluation::success(InputDecision::Preserve)
    );
}
