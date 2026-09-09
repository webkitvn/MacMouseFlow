#ifndef POINTER_INPUT_FFI_H
#define POINTER_INPUT_FFI_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define POINTER_INPUT_ABI_VERSION_V1 UINT32_C(1)

#define POINTER_INPUT_STATUS_SUCCESS_V1 UINT32_C(0)
#define POINTER_INPUT_STATUS_INVALID_ARGUMENT_V1 UINT32_C(1)
#define POINTER_INPUT_STATUS_EVALUATION_FAILED_V1 UINT32_C(2)
/* A Rust panic was contained; evaluate output remains Preserve. */
#define POINTER_INPUT_STATUS_PANIC_V1 UINT32_C(3)
/* Another create call is installing the process-wide panic hook; retry create only. */
#define POINTER_INPUT_STATUS_BUSY_V1 UINT32_C(4)

#define POINTER_INPUT_DECISION_PRESERVE_V1 UINT32_C(0)
#define POINTER_INPUT_DECISION_REPLACE_V1 UINT32_C(1)

#define POINTER_INPUT_DIRECTION_SYSTEM_V1 UINT32_C(0)
#define POINTER_INPUT_DIRECTION_REVERSE_V1 UINT32_C(1)

#define POINTER_INPUT_SOURCE_MOUSE_V1 UINT32_C(0)
#define POINTER_INPUT_SOURCE_TRACKPAD_V1 UINT32_C(1)
#define POINTER_INPUT_SOURCE_UNKNOWN_V1 UINT32_C(2)

#define POINTER_INPUT_GRANULARITY_LINE_BASED_V1 UINT32_C(0)
#define POINTER_INPUT_GRANULARITY_PIXEL_BASED_V1 UINT32_C(1)

typedef uint32_t pointer_input_status_v1;

typedef struct pointer_input_event_v1 {
    uint32_t version;
    uint32_t size;
    uint32_t source_class;
    uint32_t granularity;
    int64_t horizontal_lines;
    int64_t vertical_lines;
    uint32_t reserved[2];
} pointer_input_event_v1;

typedef struct pointer_input_configuration_v1 {
    uint32_t version;
    uint32_t size;
    uint32_t direction;
    uint32_t reserved;
} pointer_input_configuration_v1;

typedef struct pointer_input_decision_v1 {
    uint32_t version;
    uint32_t size;
    uint32_t decision;
    uint32_t reserved;
    int64_t horizontal_lines;
    int64_t vertical_lines;
} pointer_input_decision_v1;

/*
 * out_engine must point to an initially NULL owner variable. A non-NULL owner variable is
 * rejected unchanged. On success it receives the uniquely owned handle; only that owner may
 * destroy the allocation with pointer_input_engine_destroy_v1. A copied non-owning handle value
 * may call set_configuration or evaluate concurrently while the owner keeps the allocation live.
 * BUSY means only that another creator is installing the process-wide panic hook; retry create.
 */
pointer_input_status_v1 pointer_input_engine_create_v1(void **out_engine);

/* handle must refer to a live owner-retained allocation; configuration must have exact v1 layout. */
pointer_input_status_v1 pointer_input_engine_set_configuration_v1(
    void *handle,
    const pointer_input_configuration_v1 *configuration);

/*
 * handle must refer to a live owner-retained allocation. Non-owning copied handle values may call
 * this function concurrently with set_configuration. A non-null output is initialized to Preserve
 * before request validation. event must have exact v1 layout.
 */
pointer_input_status_v1 pointer_input_engine_evaluate_v1(
    void *handle,
    const pointer_input_event_v1 *event,
    pointer_input_decision_v1 *out_decision);

/*
 * Accepts a pointer to the owner's unique handle variable. It sets that variable to NULL before
 * release; passing an already-NULL owner variable is a no-op. Concurrent destruction, use after
 * destruction, stale, and fabricated pointers are caller contract violations. The owner must not
 * destroy while non-owning copied handle values are being used.
 */
pointer_input_status_v1 pointer_input_engine_destroy_v1(void **in_out_handle);

#ifdef __cplusplus
}
#endif

#endif
