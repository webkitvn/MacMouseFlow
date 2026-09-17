#ifndef MMF_TRACE_RING_H
#define MMF_TRACE_RING_H
#include <stdint.h>
#include <stdatomic.h>
#define MMF_TRACE_RING_CAPACITY 131072u
typedef struct mmf_trace_record { uint8_t kind, granularity, decision, outcome, reason; uint64_t sequence, input_sequence, t_ns, extraction_ns, rust_ns, apply_ns, total_ns; int64_t horizontal, vertical; } mmf_trace_record;
typedef struct mmf_trace_ring { _Atomic uint32_t write_index, read_index; _Atomic uint64_t drops; mmf_trace_record records[MMF_TRACE_RING_CAPACITY]; } mmf_trace_ring;
static inline void mmf_trace_ring_init(mmf_trace_ring *r) { atomic_init(&r->write_index,0); atomic_init(&r->read_index,0); atomic_init(&r->drops,0); }
static inline int mmf_trace_ring_push(mmf_trace_ring *r,const mmf_trace_record *v) { uint32_t w=atomic_load_explicit(&r->write_index,memory_order_relaxed),n=(w+1)%MMF_TRACE_RING_CAPACITY; if(n==atomic_load_explicit(&r->read_index,memory_order_acquire)){atomic_fetch_add_explicit(&r->drops,1,memory_order_relaxed);return 0;} r->records[w]=*v;atomic_store_explicit(&r->write_index,n,memory_order_release);return 1; }
static inline int mmf_trace_ring_pop(mmf_trace_ring *r,mmf_trace_record *v) { uint32_t q=atomic_load_explicit(&r->read_index,memory_order_relaxed);if(q==atomic_load_explicit(&r->write_index,memory_order_acquire))return 0;*v=r->records[q];atomic_store_explicit(&r->read_index,(q+1)%MMF_TRACE_RING_CAPACITY,memory_order_release);return 1; }
static inline uint64_t mmf_trace_ring_take_drops(mmf_trace_ring *r){return atomic_exchange_explicit(&r->drops,0,memory_order_acq_rel);}
#endif
