// Package migrations embeds the SQL migration files so they ship inside the
// compiled control-api binary (no filesystem access to a migrations
// directory is required at runtime).
package migrations

import "embed"

//go:embed *.up.sql
var FS embed.FS
