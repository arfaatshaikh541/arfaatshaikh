// Package config loads worker configuration from environment variables.
package config

import (
	"os"
	"strings"
)

type Config struct {
	KafkaBrokers  []string
	ConsumerGroup string
	Topic         string
	HealthPort    string
}

func Load() Config {
	brokers := getEnv("KAFKA_BROKERS", "localhost:19092")
	return Config{
		KafkaBrokers:  strings.Split(brokers, ","),
		ConsumerGroup: getEnv("WORKER_CONSUMER_GROUP", "gridkeep-worker-dev"),
		Topic:         getEnv("WORKER_TOPIC", "platform.heartbeat.v1"),
		HealthPort:    getEnv("WORKER_HEALTH_PORT", "8091"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
