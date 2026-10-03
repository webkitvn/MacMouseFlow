#include <assert.h>
#include <stddef.h>

#include "pointer_input_ffi.h"

_Static_assert(POINTER_INPUT_STATUS_BUSY_V2 == UINT32_C(4), "Busy status must remain 4");

_Static_assert(POINTER_INPUT_ABI_VERSION_V2 == 2, "ABI version");
_Static_assert(sizeof(pointer_input_event_v2) == 40, "event layout");
_Static_assert(sizeof(pointer_input_configuration_v2) == 20, "configuration layout");
_Static_assert(offsetof(pointer_input_configuration_v2, amount_percent) == 12, "amount offset");
_Static_assert(sizeof(pointer_input_decision_v2) == 32, "decision layout");
_Static_assert(offsetof(pointer_input_decision_v2, horizontal_hundredths) == 16, "horizontal offset");
_Static_assert(offsetof(pointer_input_decision_v2, vertical_hundredths) == 24, "vertical offset");

static pointer_input_event_v2 line_event(int64_t horizontal, int64_t vertical) {
    return (pointer_input_event_v2){
        .version = POINTER_INPUT_ABI_VERSION_V2,
        .size = sizeof(pointer_input_event_v2),
        .source_class = POINTER_INPUT_SOURCE_UNKNOWN_V2,
        .granularity = POINTER_INPUT_GRANULARITY_LINE_BASED_V2,
        .horizontal_lines = horizontal,
        .vertical_lines = vertical,
        .reserved = {0, 0},
    };
}

int main(void) {
    void *engine = NULL;
    pointer_input_configuration_v2 reverse = {
        .version = POINTER_INPUT_ABI_VERSION_V2,
        .size = sizeof(pointer_input_configuration_v2),
        .direction = POINTER_INPUT_DIRECTION_REVERSE_V2,
        .amount_percent = 100,
        .reserved = 0,
    };
    pointer_input_decision_v2 output = {0};
    pointer_input_event_v2 event = line_event(0, 3);

    assert(pointer_input_configuration_validate_v2(&reverse) == POINTER_INPUT_STATUS_SUCCESS_V2);
    reverse.reserved = 1;
    assert(pointer_input_configuration_validate_v2(&reverse) == POINTER_INPUT_STATUS_INVALID_ARGUMENT_V2);
    reverse.reserved = 0;
    assert(pointer_input_configuration_validate_v2(NULL) == POINTER_INPUT_STATUS_INVALID_ARGUMENT_V2);
    assert(pointer_input_engine_create_v2(&engine) == POINTER_INPUT_STATUS_SUCCESS_V2);
    assert(engine != NULL);
    void *owner = engine;
    assert(pointer_input_engine_create_v2(&engine) == POINTER_INPUT_STATUS_INVALID_ARGUMENT_V2);
    assert(engine == owner);
    assert(pointer_input_engine_set_configuration_v2(engine, &reverse) == POINTER_INPUT_STATUS_SUCCESS_V2);
    assert(pointer_input_engine_evaluate_v2(engine, &event, &output) == POINTER_INPUT_STATUS_SUCCESS_V2);
    assert(output.decision == POINTER_INPUT_DECISION_REPLACE_V2);
    assert(output.horizontal_hundredths == 0);
    assert(output.vertical_hundredths == -300);

    event = line_event(0, 0);
    assert(pointer_input_engine_evaluate_v2(engine, &event, &output) == POINTER_INPUT_STATUS_SUCCESS_V2);
    assert(output.decision == POINTER_INPUT_DECISION_PRESERVE_V2);

    event.granularity = POINTER_INPUT_GRANULARITY_PIXEL_BASED_V2;
    event.horizontal_lines = 4;
    event.vertical_lines = -6;
    assert(pointer_input_engine_evaluate_v2(engine, &event, &output) == POINTER_INPUT_STATUS_SUCCESS_V2);
    assert(output.decision == POINTER_INPUT_DECISION_PRESERVE_V2);

    event.size--;
    output.decision = POINTER_INPUT_DECISION_REPLACE_V2;
    assert(pointer_input_engine_evaluate_v2(engine, &event, &output) == POINTER_INPUT_STATUS_INVALID_ARGUMENT_V2);
    assert(output.decision == POINTER_INPUT_DECISION_PRESERVE_V2);

    assert(pointer_input_engine_destroy_v2(&engine) == POINTER_INPUT_STATUS_SUCCESS_V2);
    assert(engine == NULL);
    assert(pointer_input_engine_destroy_v2(&engine) == POINTER_INPUT_STATUS_SUCCESS_V2);
    return 0;
}
