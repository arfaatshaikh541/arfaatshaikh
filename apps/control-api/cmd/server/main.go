// Command server runs the GRIDKEEP control-api: a modular monolith serving
// identity, tenancy, operators, RBAC, subscriptions, audit, and platform
// administration for Milestone 1.
package main

import (
	"context"
	"encoding/base64"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"gridkeep/control-api/internal/app"
	"gridkeep/control-api/internal/platform/cache"
	"gridkeep/control-api/internal/platform/config"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/logging"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		panic(err)
	}
	logger := logging.New(cfg.Env)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	store, err := dbpkg.Connect(ctx, cfg.DatabaseURL)
	if err != nil {
		logger.Error("failed to connect to database", "error", err)
		os.Exit(1)
	}
	defer store.Close()

	applied, err := store.Migrate(ctx)
	if err != nil {
		logger.Error("failed to run migrations", "error", err)
		os.Exit(1)
	}
	logger.Info("migrations applied", "count", len(applied), "versions", applied)

	cacheClient, err := cache.Connect(ctx, cfg.RedisURL)
	if err != nil {
		logger.Error("failed to connect to redis", "error", err)
		os.Exit(1)
	}
	defer func() { _ = cacheClient.Close() }()

	mfaKey, err := loadMFAKey()
	if err != nil {
		logger.Error("failed to load MFA encryption key", "error", err)
		os.Exit(1)
	}

	router := app.NewRouter(app.Deps{
		Store:  store,
		Cache:  cacheClient,
		Logger: logger,
		Config: cfg,
		MFAKey: mfaKey,
	})

	srv := &http.Server{
		Addr:              cfg.Host + ":" + cfg.Port,
		Handler:           router,
		ReadHeaderTimeout: 10 * time.Second,
	}

	go func() {
		logger.Info("control-api listening", "addr", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("server error", "error", err)
			os.Exit(1)
		}
	}()

	<-ctx.Done()
	logger.Info("shutting down")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = srv.Shutdown(shutdownCtx)
}

// loadMFAKey reads MFA_ENCRYPTION_KEY (base64-encoded 32 bytes) from the
// environment. It is required in every environment -- there is no insecure
// fallback.
func loadMFAKey() ([]byte, error) {
	raw := os.Getenv("MFA_ENCRYPTION_KEY")
	if raw == "" {
		return nil, errors.New("MFA_ENCRYPTION_KEY environment variable is required (base64-encoded 32-byte key)")
	}
	key, err := base64.StdEncoding.DecodeString(raw)
	if err != nil {
		return nil, errors.New("MFA_ENCRYPTION_KEY must be valid base64")
	}
	return key, nil
}
