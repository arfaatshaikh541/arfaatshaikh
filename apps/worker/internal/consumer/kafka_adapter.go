package consumer

import (
	"context"

	kafka "github.com/segmentio/kafka-go"
)

// KafkaReader adapts *kafka.Reader to the Reader interface. The underlying
// kafka.Message (needed for a real offset commit) is round-tripped through
// Message.raw rather than re-fetched, so CommitMessage commits the exact
// message that was fetched and processed.
type KafkaReader struct {
	reader *kafka.Reader
}

func NewKafkaReader(brokers []string, topic, groupID string) *KafkaReader {
	return &KafkaReader{
		reader: kafka.NewReader(kafka.ReaderConfig{
			Brokers: brokers,
			Topic:   topic,
			GroupID: groupID,
		}),
	}
}

func (k *KafkaReader) FetchMessage(ctx context.Context) (Message, error) {
	m, err := k.reader.FetchMessage(ctx)
	if err != nil {
		return Message{}, err
	}
	return Message{Key: string(m.Key), Value: m.Value, raw: m}, nil
}

func (k *KafkaReader) CommitMessage(ctx context.Context, msg Message) error {
	raw, ok := msg.raw.(kafka.Message)
	if !ok {
		// A message not obtained from this reader (e.g. constructed in a
		// test) has nothing to commit against.
		return nil
	}
	return k.reader.CommitMessages(ctx, raw)
}

func (k *KafkaReader) Close() error {
	return k.reader.Close()
}

// KafkaDeadLetterWriter adapts *kafka.Writer to the DeadLetterWriter interface.
type KafkaDeadLetterWriter struct {
	writer *kafka.Writer
}

func NewKafkaDeadLetterWriter(brokers []string, topic string) *KafkaDeadLetterWriter {
	return &KafkaDeadLetterWriter{
		writer: &kafka.Writer{
			Addr:     kafka.TCP(brokers...),
			Topic:    topic,
			Balancer: &kafka.LeastBytes{},
		},
	}
}

func (k *KafkaDeadLetterWriter) WriteDeadLetter(ctx context.Context, msg Message, reason string) error {
	return k.writer.WriteMessages(ctx, kafka.Message{
		Key:   []byte(msg.Key),
		Value: msg.Value,
		Headers: []kafka.Header{
			{Key: "x-dead-letter-reason", Value: []byte(reason)},
		},
	})
}

func (k *KafkaDeadLetterWriter) Close() error {
	return k.writer.Close()
}
