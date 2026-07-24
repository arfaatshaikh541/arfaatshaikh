// Package config loads control-api configuration exclusively from environment
// variables. No secret ever has a hardcoded production default: every
// security-sensitive value must be supplied by the environment or the
// process fails to start.
package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	Env         string
	Host        string
	Port        string
	MetricsPort string

	DatabaseURL string

	RedisURL string

	SessionCookieName   string
	SessionCookieSecure bool
	SessionTTL          time.Duration
	StepUpTTL           time.Duration

	CORSAllowedOrigins []string

	Argon2Memory      uint32
	Argon2Iterations  uint32
	Argon2Parallelism uint8

	LoginLockoutThreshold int
	LoginLockoutWindow    time.Duration
	EmailVerificationTTL  time.Duration
	PasswordResetTTL      time.Duration
	MFAMaxAttempts        int

	AgentBootstrapTokenTTL time.Duration
	AgentCertificateTTL    time.Duration

	PolicyEngineURL     string
	PolicyEngineTimeout time.Duration

	S3Endpoint               string
	S3Region                 string
	S3AccessKey              string
	S3SecretKey              string
	S3BucketArtefacts        string
	S3UseSSL                 bool
	ArtefactUploadURLTTL     time.Duration
	ArtefactDownloadURLTTL   time.Duration
	ArtefactMaxContentLength int64

	SMTPHost string
	SMTPPort string
	SMTPFrom string
}

func Load() (*Config, error) {
	cfg := &Config{
		Env:                 getEnv("CONTROL_API_ENV", "development"),
		Host:                getEnv("CONTROL_API_HOST", "0.0.0.0"),
		Port:                getEnv("CONTROL_API_PORT", "8080"),
		MetricsPort:         getEnv("CONTROL_API_METRICS_PORT", "9090"),
		DatabaseURL:         os.Getenv("DATABASE_URL"),
		RedisURL:            getEnv("REDIS_URL", "redis://localhost:6379/0"),
		SessionCookieName:   getEnv("SESSION_COOKIE_NAME", "gridkeep_session"),
		SessionCookieSecure: getEnvBool("SESSION_COOKIE_SECURE", true),
		SMTPHost:            getEnv("SMTP_HOST", "localhost"),
		SMTPPort:            getEnv("SMTP_PORT", "1025"),
		SMTPFrom:            getEnv("SMTP_FROM", "no-reply@gridkeep.local"),
		PolicyEngineURL:     getEnv("POLICY_ENGINE_URL", "http://localhost:8090"),
		S3Endpoint:          getEnv("S3_ENDPOINT", "http://localhost:9000"),
		S3Region:            getEnv("S3_REGION", "us-east-1"),
		S3AccessKey:         os.Getenv("S3_ACCESS_KEY"),
		S3SecretKey:         os.Getenv("S3_SECRET_KEY"),
		S3BucketArtefacts:   getEnv("S3_BUCKET_ARTEFACTS", "gridkeep-artefacts"),
		S3UseSSL:            getEnvBool("S3_USE_SSL", false),
	}

	if cfg.DatabaseURL == "" {
		return nil, fmt.Errorf("DATABASE_URL is required")
	}
	if cfg.S3AccessKey == "" || cfg.S3SecretKey == "" {
		return nil, fmt.Errorf("S3_ACCESS_KEY and S3_SECRET_KEY are required")
	}

	var err error
	if cfg.SessionTTL, err = getEnvDurationHours("SESSION_TTL_HOURS", 12); err != nil {
		return nil, err
	}
	if cfg.StepUpTTL, err = getEnvDurationMinutes("STEP_UP_TTL_MINUTES", 15); err != nil {
		return nil, err
	}
	if cfg.EmailVerificationTTL, err = getEnvDurationHours("EMAIL_VERIFICATION_TTL_HOURS", 24); err != nil {
		return nil, err
	}
	if cfg.PasswordResetTTL, err = getEnvDurationMinutes("PASSWORD_RESET_TTL_MINUTES", 30); err != nil {
		return nil, err
	}
	if cfg.LoginLockoutWindow, err = getEnvDurationMinutes("LOGIN_LOCKOUT_WINDOW_MINUTES", 15); err != nil {
		return nil, err
	}
	if cfg.AgentBootstrapTokenTTL, err = getEnvDurationHours("AGENT_BOOTSTRAP_TOKEN_TTL_HOURS", 24); err != nil {
		return nil, err
	}
	if cfg.AgentCertificateTTL, err = getEnvDurationHours("AGENT_CERTIFICATE_TTL_HOURS", 72); err != nil {
		return nil, err
	}
	if cfg.PolicyEngineTimeout, err = getEnvDurationSeconds("POLICY_ENGINE_TIMEOUT_SECONDS", 5); err != nil {
		return nil, err
	}
	if cfg.ArtefactUploadURLTTL, err = getEnvDurationMinutes("ARTEFACT_UPLOAD_URL_TTL_MINUTES", 15); err != nil {
		return nil, err
	}
	if cfg.ArtefactDownloadURLTTL, err = getEnvDurationMinutes("ARTEFACT_DOWNLOAD_URL_TTL_MINUTES", 15); err != nil {
		return nil, err
	}
	cfg.ArtefactMaxContentLength = getEnvInt64("ARTEFACT_MAX_CONTENT_LENGTH_BYTES", 20*1024*1024*1024)

	cfg.LoginLockoutThreshold = getEnvInt("LOGIN_LOCKOUT_THRESHOLD", 5)
	cfg.MFAMaxAttempts = getEnvInt("MFA_MAX_ATTEMPTS", 5)

	argon2Memory := getEnvInt("ARGON2_MEMORY_KIB", 65536)
	argon2Iterations := getEnvInt("ARGON2_ITERATIONS", 3)
	argon2Parallelism := getEnvInt("ARGON2_PARALLELISM", 2)
	cfg.Argon2Memory = uint32(argon2Memory)
	cfg.Argon2Iterations = uint32(argon2Iterations)
	cfg.Argon2Parallelism = uint8(argon2Parallelism)

	origins := getEnv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
	for _, o := range strings.Split(origins, ",") {
		o = strings.TrimSpace(o)
		if o != "" {
			cfg.CORSAllowedOrigins = append(cfg.CORSAllowedOrigins, o)
		}
	}

	return cfg, nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvBool(key string, fallback bool) bool {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	b, err := strconv.ParseBool(v)
	if err != nil {
		return fallback
	}
	return b
}

func getEnvInt(key string, fallback int) int {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	i, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return i
}

func getEnvInt64(key string, fallback int64) int64 {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	i, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return fallback
	}
	return i
}

func getEnvDurationHours(key string, fallbackHours int) (time.Duration, error) {
	v := getEnvInt(key, fallbackHours)
	if v <= 0 {
		return 0, fmt.Errorf("%s must be a positive integer", key)
	}
	return time.Duration(v) * time.Hour, nil
}

func getEnvDurationMinutes(key string, fallbackMinutes int) (time.Duration, error) {
	v := getEnvInt(key, fallbackMinutes)
	if v <= 0 {
		return 0, fmt.Errorf("%s must be a positive integer", key)
	}
	return time.Duration(v) * time.Minute, nil
}

func getEnvDurationSeconds(key string, fallbackSeconds int) (time.Duration, error) {
	v := getEnvInt(key, fallbackSeconds)
	if v <= 0 {
		return 0, fmt.Errorf("%s must be a positive integer", key)
	}
	return time.Duration(v) * time.Second, nil
}
