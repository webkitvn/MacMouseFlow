#include <assert.h>
#include <stddef.h>

#include "pointer_input_ffi.h"

static pointer_input_event_v1 line_event(int64_t horizontal, int64_t vertical) {
    return (pointer_input_event_v1){
        .version = POINTER_INPUT_ABI_VERSION_V1,
        .size = sizeof(pointer_input_event_v1),
        .source_class = POINTER_INPUT_SOURCE_UNKNOWN_V1,
        .granularity = POINTER_INPUT_GRANULARITY_LINE_BASED_V1,
        .horizontal_lines = horizontal,
        .vertical_lines = vertical,
        .reserved = {0, 0},
    };
}

int main(void) {
    void *engine = NULL;
    pointer_input_configuration_v1 reverse = {
        .version = POINTER_INPUT_ABI_VERSION_V1,
        .size = sizeof(pointer_input_configuration_v1),
        .direction = POINTER_INPUT_DIRECTION_REVERSE_V1,
        .reserved = 0,
    };
    pointer_input_decision_v1 output = {0};
    pointer_input_event_v1 event = line_event(0, 3);

    assert(pointer_input_engine_create_v1(&engine) == POINTER_INPUT_STATUS_SUCCESS_V1);
    assert(engine != NULL);
    assert(pointer_input_engine_set_configuration_v1(engine, &reverse) == POINTER_INPUT_STATUS_SUCCESS_V1);
    assert(pointer_input_engine_evaluate_v1(engine, &event, &output) == POINTER_INPUT_STATUS_SUCCESS_V1);
    assert(output.decision == POINTER_INPUT_DECISION_REPLACE_V1);
    assert(output.horizontal_lines == 0);
    assert(output.vertical_lines == -3);

    event = line_event(0, 0);
    assert(pointer_input_engine_evaluate_v1(engine, &event, &output) == POINTER_INPUT_STATUS_SUCCESS_V1);
    assert(output.decision == POINTER_INPUT_DECISION_PRESERVE_V1);

    event.granularity = POINTER_INPUT_GRANULARITY_PIXEL_BASED_V1;
    event.horizontal_lines = 4;
    event.vertical_lines = -6;
    assert(pointer_input_engine_evaluate_v1(engine, &event, &output) == POINTER_INPUT_STATUS_SUCCESS_V1);
    assert(output.decision == POINTER_INPUT_DECISION_PRESERVE_V1);

    event.size--;
    output.decision = POINTER_INPUT_DECISION_REPLACE_V1;
    assert(pointer_input_engine_evaluate_v1(engine, &event, &output) == POINTER_INPUT_STATUS_INVALID_ARGUMENT_V1);
    assert(output.decision == POINTER_INPUT_DECISION_PRESERVE_V1);

    assert(pointer_input_engine_destroy_v1(&engine) == POINTER_INPUT_STATUS_SUCCESS_V1);
    assert(engine == NULL);
    assert(pointer_input_engine_destroy_v1(&engine) == POINTER_INPUT_STATUS_SUCCESS_V1);
    return 0;
}
