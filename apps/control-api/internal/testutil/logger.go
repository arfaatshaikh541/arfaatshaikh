package testutil

import (
	"io"
	"log/slog"
)

// DiscardLogger returns a logger that writes nowhere, for tests that need
// to supply one but don't want output cluttering `go test` results.
func DiscardLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}
