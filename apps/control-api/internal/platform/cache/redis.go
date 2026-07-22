// Package cache wraps Redis for rate-limit counters and short-TTL read
// caches (e.g. resolved entitlements). Redis is never the source of truth
// for any security or billing decision — it only accelerates re-derivable
// reads and enforces time-windowed counters.
package cache

import (
	"context"
	"fmt"

	"github.com/redis/go-redis/v9"
)

type Client struct {
	rdb *redis.Client
}

func Connect(ctx context.Context, redisURL string) (*Client, error) {
	opts, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, fmt.Errorf("parse redis url: %w", err)
	}
	rdb := redis.NewClient(opts)
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("ping redis: %w", err)
	}
	return &Client{rdb: rdb}, nil
}

func (c *Client) Close() error {
	return c.rdb.Close()
}

func (c *Client) Raw() *redis.Client {
	return c.rdb
}
