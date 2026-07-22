package db

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io/fs"
	"sort"
	"strings"

	"gridkeep/control-api/migrations"
)

var migrationsFS = migrations.FS

const migrationsDir = "."

type migrationFile struct {
	Version  string
	Filename string
	SQL      string
}

// Migrate applies every embedded *.up.sql migration that has not yet been
// recorded in schema_migrations, in filename order, each inside its own
// transaction. It is safe to call on every process start (idempotent).
func (s *Store) Migrate(ctx context.Context) ([]string, error) {
	if _, err := s.Pool.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS schema_migrations (
			version    TEXT PRIMARY KEY,
			checksum   TEXT NOT NULL,
			applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)
	`); err != nil {
		return nil, fmt.Errorf("ensure schema_migrations table: %w", err)
	}

	files, err := loadMigrationFiles()
	if err != nil {
		return nil, err
	}

	applied := map[string]string{}
	rows, err := s.Pool.Query(ctx, `SELECT version, checksum FROM schema_migrations`)
	if err != nil {
		return nil, fmt.Errorf("load applied migrations: %w", err)
	}
	for rows.Next() {
		var version, checksum string
		if err := rows.Scan(&version, &checksum); err != nil {
			rows.Close()
			return nil, fmt.Errorf("scan applied migration: %w", err)
		}
		applied[version] = checksum
	}
	rows.Close()

	var appliedNow []string
	for _, f := range files {
		sum := checksum(f.SQL)
		if existing, ok := applied[f.Version]; ok {
			if existing != sum {
				return nil, fmt.Errorf("migration %s has changed since it was applied (checksum mismatch)", f.Version)
			}
			continue
		}

		tx, err := s.Pool.Begin(ctx)
		if err != nil {
			return nil, fmt.Errorf("begin migration tx for %s: %w", f.Version, err)
		}
		if _, err := tx.Exec(ctx, f.SQL); err != nil {
			_ = tx.Rollback(ctx)
			return nil, fmt.Errorf("apply migration %s: %w", f.Version, err)
		}
		if _, err := tx.Exec(ctx,
			`INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)`,
			f.Version, sum,
		); err != nil {
			_ = tx.Rollback(ctx)
			return nil, fmt.Errorf("record migration %s: %w", f.Version, err)
		}
		if err := tx.Commit(ctx); err != nil {
			return nil, fmt.Errorf("commit migration %s: %w", f.Version, err)
		}
		appliedNow = append(appliedNow, f.Version)
	}

	return appliedNow, nil
}

func loadMigrationFiles() ([]migrationFile, error) {
	entries, err := fs.ReadDir(migrationsFS, migrationsDir)
	if err != nil {
		return nil, fmt.Errorf("read migrations dir: %w", err)
	}

	var files []migrationFile
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".up.sql") {
			continue
		}
		content, err := migrationsFS.ReadFile(e.Name())
		if err != nil {
			return nil, fmt.Errorf("read migration %s: %w", e.Name(), err)
		}
		version := strings.TrimSuffix(e.Name(), ".up.sql")
		files = append(files, migrationFile{
			Version:  version,
			Filename: e.Name(),
			SQL:      string(content),
		})
	}

	sort.Slice(files, func(i, j int) bool { return files[i].Version < files[j].Version })
	return files, nil
}

func checksum(sql string) string {
	sum := sha256.Sum256([]byte(sql))
	return hex.EncodeToString(sum[:])
}
