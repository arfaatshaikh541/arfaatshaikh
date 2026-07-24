# syntax=docker/dockerfile:1

# Multi-stage build: the builder stage never ships. Migrations are
# go:embed'd into the binary (see migrations/embed.go), so the final image
# needs nothing but the compiled binaries -- no source, no build tools, no
# migration files on disk.
FROM golang:1.25-alpine AS builder

WORKDIR /src

RUN apk add --no-cache git

COPY go.mod go.sum ./
RUN go mod download

COPY . .

# CGO_ENABLED=0 for a fully static binary that runs on the distroless
# runtime image below (no libc present there to link against dynamically).
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/server ./cmd/server
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/seed ./cmd/seed

# Distroless: no shell, no package manager, no coreutils -- nothing an
# attacker who achieves code execution inside the container could use to
# pull in further tooling. nonroot variant runs as uid/gid 65532.
FROM gcr.io/distroless/static-debian12:nonroot AS runtime

WORKDIR /app
COPY --from=builder /out/server /app/server
COPY --from=builder /out/seed /app/seed

USER nonroot:nonroot

EXPOSE 8080

ENTRYPOINT ["/app/server"]
