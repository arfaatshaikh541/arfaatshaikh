package consumer

import (
	"container/list"
	"context"
	"sync"
)

// MemoryIdempotencyStore is a bounded, in-process idempotency cache. It is a
// real, working implementation suitable for this Milestone 1 foundation
// (single worker instance, best-effort dedupe); a multi-instance deployment
// needs a shared store (Redis/Postgres), which lands alongside the first
// real event contracts in a later milestone.
type MemoryIdempotencyStore struct {
	mu       sync.Mutex
	capacity int
	order    *list.List
	index    map[string]*list.Element
}

func NewMemoryIdempotencyStore(capacity int) *MemoryIdempotencyStore {
	return &MemoryIdempotencyStore{
		capacity: capacity,
		order:    list.New(),
		index:    make(map[string]*list.Element),
	}
}

func (s *MemoryIdempotencyStore) Seen(_ context.Context, key string) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	_, ok := s.index[key]
	return ok, nil
}

func (s *MemoryIdempotencyStore) MarkSeen(_ context.Context, key string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.index[key]; ok {
		return nil
	}
	elem := s.order.PushBack(key)
	s.index[key] = elem
	if s.order.Len() > s.capacity {
		oldest := s.order.Front()
		if oldest != nil {
			s.order.Remove(oldest)
			delete(s.index, oldest.Value.(string))
		}
	}
	return nil
}
