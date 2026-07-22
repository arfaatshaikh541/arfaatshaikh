// Command worker runs the GRIDKEEP generic background job runner. Milestone
// 1 scope: idempotent-consumer foundation (fetch/dedupe/retry/dead-letter)
// wired to Redpanda, plus a health endpoint. No production event contracts
// are consumed yet -- those land alongside the modules that emit them in
// later milestones.
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"gridkeep/worker/internal/config"
	"gridkeep/worker/internal/consumer"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	cfg := config.Load()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	reader := consumer.NewKafkaReader(cfg.KafkaBrokers, cfg.Topic, cfg.ConsumerGroup)
	defer func() { _ = reader.Close() }()

	dlq := consumer.NewKafkaDeadLetterWriter(cfg.KafkaBrokers, cfg.Topic+".dead-letter")
	defer func() { _ = dlq.Close() }()

	runner := &consumer.Runner{
		Reader:      reader,
		DeadLetter:  dlq,
		Idempotency: consumer.NewMemoryIdempotencyStore(10_000),
		Handle: func(ctx context.Context, msg consumer.Message) error {
			logger.InfoContext(ctx, "message received", "key", msg.Key, "size", len(msg.Value))
			return nil
		},
		MaxAttempts: 3,
		BaseBackoff: 500 * time.Millisecond,
		Logger:      logger,
	}

	healthSrv := &http.Server{
		Addr: ":" + cfg.HealthPort,
		Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"status":"ok"}`))
		}),
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		if err := healthSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("health server error", "error", err)
		}
	}()

	go func() {
		if err := runner.Run(ctx); err != nil && !errors.Is(err, consumer.ErrStopped) {
			logger.Error("consumer runner exited with error", "error", err)
		}
	}()

	logger.Info("worker started", "topic", cfg.Topic, "consumer_group", cfg.ConsumerGroup, "brokers", cfg.KafkaBrokers)

	<-ctx.Done()
	logger.Info("shutting down")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = healthSrv.Shutdown(shutdownCtx)
}
