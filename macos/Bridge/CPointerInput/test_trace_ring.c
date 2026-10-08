#include "mmf_trace_ring.h"
#include <assert.h>
#include <stdlib.h>
int main(void) {
  mmf_trace_ring *ring = malloc(sizeof(*ring)); assert(ring); mmf_trace_ring_init(ring);
  mmf_trace_record value = {0}, out = {0};
  for (unsigned i = 0; i < MMF_TRACE_RING_CAPACITY - 1; ++i) { value.sequence = i; assert(mmf_trace_ring_push(ring, &value)); }
  assert(!mmf_trace_ring_push(ring, &value)); assert(mmf_trace_ring_take_drops(ring) == 1);
  for (unsigned i = 0; i < MMF_TRACE_RING_CAPACITY - 1; ++i) { assert(mmf_trace_ring_pop(ring, &out)); assert(out.sequence == i); }
  assert(!mmf_trace_ring_pop(ring, &out));
  value.sequence = 99; value.direction = 1; value.amount_percent = 137; value.decision_horizontal = -548; value.decision_vertical = 274; assert(mmf_trace_ring_push(ring, &value)); assert(mmf_trace_ring_pop(ring, &out)); assert(out.sequence == 99 && out.direction == 1 && out.amount_percent == 137 && out.decision_horizontal == -548 && out.decision_vertical == 274);
  free(ring); return 0;
}
