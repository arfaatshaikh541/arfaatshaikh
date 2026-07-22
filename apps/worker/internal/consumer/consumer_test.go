package consumer

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"
)

type fakeReader struct {
	messages  []Message
	pos       int
	committed []Message
}

func (f *fakeReader) FetchMessage(ctx context.Context) (Message, error) {
	if f.pos >= len(f.messages) {
		<-ctx.Done()
		return Message{}, context.Canceled
	}
	msg := f.messages[f.pos]
	f.pos++
	return msg, nil
}

func (f *fakeReader) CommitMessage(ctx context.Context, msg Message) error {
	f.committed = append(f.committed, msg)
	return nil
}

type fakeDeadLetter struct {
	written []Message
	reasons []string
}

func (f *fakeDeadLetter) WriteDeadLetter(ctx context.Context, msg Message, reason string) error {
	f.written = append(f.written, msg)
	f.reasons = append(f.reasons, reason)
	return nil
}

func silentLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

func TestProcessOne_SuccessCommitsAndMarksSeen(t *testing.T) {
	reader := &fakeReader{}
	idem := NewMemoryIdempotencyStore(10)
	var handled []string

	r := &Runner{
		Reader:      reader,
		Idempotency: idem,
		Handle: func(ctx context.Context, msg Message) error {
			handled = append(handled, msg.Key)
			return nil
		},
		MaxAttempts: 3,
		BaseBackoff: time.Millisecond,
		Logger:      silentLogger(),
	}

	msg := Message{Key: "evt-1", Value: []byte("payload")}
	if err := r.processOne(context.Background(), msg); err != nil {
		t.Fatalf("processOne returned error: %v", err)
	}

	if len(handled) != 1 {
		t.Fatalf("expected handler called once, got %d", len(handled))
	}
	if len(reader.committed) != 1 {
		t.Fatalf("expected message committed once, got %d", len(reader.committed))
	}
	seen, _ := idem.Seen(context.Background(), "evt-1")
	if !seen {
		t.Fatal("expected key marked as seen after success")
	}
}

func TestProcessOne_DuplicateKeyIsSkippedNotReprocessed(t *testing.T) {
	reader := &fakeReader{}
	idem := NewMemoryIdempotencyStore(10)
	callCount := 0

	r := &Runner{
		Reader:      reader,
		Idempotency: idem,
		Handle: func(ctx context.Context, msg Message) error {
			callCount++
			return nil
		},
		MaxAttempts: 3,
		BaseBackoff: time.Millisecond,
		Logger:      silentLogger(),
	}

	msg := Message{Key: "evt-dup", Value: []byte("payload")}
	if err := r.processOne(context.Background(), msg); err != nil {
		t.Fatalf("first processOne returned error: %v", err)
	}
	if err := r.processOne(context.Background(), msg); err != nil {
		t.Fatalf("second (redelivered) processOne returned error: %v", err)
	}

	if callCount != 1 {
		t.Fatalf("expected handler invoked exactly once despite redelivery, got %d", callCount)
	}
	if len(reader.committed) != 2 {
		t.Fatalf("expected both deliveries committed (first processed, second skipped-but-acked), got %d", len(reader.committed))
	}
}

func TestProcessOne_ExhaustsRetriesThenDeadLetters(t *testing.T) {
	reader := &fakeReader{}
	dlq := &fakeDeadLetter{}
	idem := NewMemoryIdempotencyStore(10)
	attempts := 0
	wantErr := errors.New("downstream unavailable")

	r := &Runner{
		Reader:      reader,
		DeadLetter:  dlq,
		Idempotency: idem,
		Handle: func(ctx context.Context, msg Message) error {
			attempts++
			return wantErr
		},
		MaxAttempts: 3,
		BaseBackoff: time.Millisecond,
		Logger:      silentLogger(),
	}

	msg := Message{Key: "evt-poison", Value: []byte("payload")}
	if err := r.processOne(context.Background(), msg); err != nil {
		t.Fatalf("processOne returned error: %v", err)
	}

	if attempts != 3 {
		t.Fatalf("expected exactly MaxAttempts=3 handler invocations, got %d", attempts)
	}
	if len(dlq.written) != 1 {
		t.Fatalf("expected message dead-lettered once, got %d", len(dlq.written))
	}
	if dlq.reasons[0] != wantErr.Error() {
		t.Fatalf("expected dead-letter reason %q, got %q", wantErr.Error(), dlq.reasons[0])
	}
	if len(reader.committed) != 1 {
		t.Fatalf("expected poison message still committed after dead-lettering, got %d", len(reader.committed))
	}
	seen, _ := idem.Seen(context.Background(), "evt-poison")
	if seen {
		t.Fatal("a failed (dead-lettered) message must not be marked seen")
	}
}

func TestBackoffDuration_DoublesPerAttempt(t *testing.T) {
	base := 10 * time.Millisecond
	cases := map[int]time.Duration{
		1: 10 * time.Millisecond,
		2: 20 * time.Millisecond,
		3: 40 * time.Millisecond,
	}
	for attempt, want := range cases {
		if got := backoffDuration(base, attempt); got != want {
			t.Errorf("backoffDuration(%v, %d) = %v, want %v", base, attempt, got, want)
		}
	}
}
