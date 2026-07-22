// Package consumer implements the worker's idempotent-consumer pattern:
// fetch -> check idempotency key -> handle with retry+backoff -> commit, or
// route to a dead-letter topic after exhausting retries. It is deliberately
// decoupled from the concrete Kafka client via small interfaces so the
// control flow can be unit-tested without a live broker.
package consumer

import (
	"context"
	"errors"
	"log/slog"
	"time"
)

// Message is the minimal shape the runner needs from a broker message. raw
// carries the concrete client message (e.g. kafka.Message) so a Reader
// implementation can commit the exact fetched message later; it is opaque
// to the runner and to test fakes.
type Message struct {
	Key   string
	Value []byte
	raw   any
}

// Reader is satisfied by a Kafka consumer (e.g. *kafka.Reader).
type Reader interface {
	FetchMessage(ctx context.Context) (Message, error)
	CommitMessage(ctx context.Context, msg Message) error
}

// DeadLetterWriter is satisfied by a Kafka producer bound to a dead-letter topic.
type DeadLetterWriter interface {
	WriteDeadLetter(ctx context.Context, msg Message, reason string) error
}

// IdempotencyStore records which message keys have already been processed
// successfully, so redelivery (at-least-once semantics) never double-applies
// a side effect.
type IdempotencyStore interface {
	Seen(ctx context.Context, key string) (bool, error)
	MarkSeen(ctx context.Context, key string) error
}

// Handler processes a single message. It must be safe to call more than
// once for the same message up until it returns nil (the runner only calls
// MarkSeen after a nil return).
type Handler func(ctx context.Context, msg Message) error

type Runner struct {
	Reader      Reader
	DeadLetter  DeadLetterWriter
	Idempotency IdempotencyStore
	Handle      Handler
	MaxAttempts int
	BaseBackoff time.Duration
	Logger      *slog.Logger
}

// ErrStopped is returned by Run when ctx is cancelled cleanly.
var ErrStopped = errors.New("consumer stopped")

// Run loops fetching messages until ctx is cancelled. Each message is
// processed via processOne; a fetch error other than context cancellation
// is logged and retried after a short pause (the loop never exits on a
// transient broker error).
func (r *Runner) Run(ctx context.Context) error {
	for {
		select {
		case <-ctx.Done():
			return ErrStopped
		default:
		}

		msg, err := r.Reader.FetchMessage(ctx)
		if err != nil {
			if errors.Is(err, context.Canceled) {
				return ErrStopped
			}
			r.Logger.ErrorContext(ctx, "fetch message failed", "error", err)
			time.Sleep(r.BaseBackoff)
			continue
		}

		if err := r.processOne(ctx, msg); err != nil {
			r.Logger.ErrorContext(ctx, "message processing abandoned after retries", "key", msg.Key, "error", err)
		}
	}
}

func (r *Runner) processOne(ctx context.Context, msg Message) error {
	seen, err := r.Idempotency.Seen(ctx, msg.Key)
	if err != nil {
		return err
	}
	if seen {
		r.Logger.InfoContext(ctx, "skipping duplicate message", "key", msg.Key)
		return r.Reader.CommitMessage(ctx, msg)
	}

	var lastErr error
	for attempt := 1; attempt <= r.MaxAttempts; attempt++ {
		lastErr = r.Handle(ctx, msg)
		if lastErr == nil {
			if err := r.Idempotency.MarkSeen(ctx, msg.Key); err != nil {
				return err
			}
			return r.Reader.CommitMessage(ctx, msg)
		}
		r.Logger.WarnContext(ctx, "handler failed, retrying", "key", msg.Key, "attempt", attempt, "error", lastErr)
		time.Sleep(backoffDuration(r.BaseBackoff, attempt))
	}

	if r.DeadLetter != nil {
		if dlqErr := r.DeadLetter.WriteDeadLetter(ctx, msg, lastErr.Error()); dlqErr != nil {
			return dlqErr
		}
	}
	// Commit even on final failure (after dead-lettering) so the consumer
	// group does not stall indefinitely reprocessing a poison message.
	return r.Reader.CommitMessage(ctx, msg)
}

func backoffDuration(base time.Duration, attempt int) time.Duration {
	d := base
	for i := 1; i < attempt; i++ {
		d *= 2
	}
	return d
}
