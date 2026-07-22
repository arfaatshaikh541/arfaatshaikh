// Package apierror defines the structured error model returned to clients.
// Internal error details (stack traces, SQL errors, file paths) are never
// serialized to the client — only a stable code, a safe message, and
// optional non-sensitive field-level details.
package apierror

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
)

type Code string

const (
	CodeValidation        Code = "VALIDATION_ERROR"
	CodeUnauthenticated   Code = "UNAUTHENTICATED"
	CodeForbidden         Code = "FORBIDDEN"
	CodeNotFound          Code = "NOT_FOUND"
	CodeConflict          Code = "CONFLICT"
	CodeRateLimited       Code = "RATE_LIMITED"
	CodeStepUpRequired    Code = "STEP_UP_REQUIRED"
	CodeEntitlementDenied Code = "ENTITLEMENT_DENIED"
	CodeInternal          Code = "INTERNAL_ERROR"
)

// APIError is the structured, client-safe error shape. httpStatus is never
// serialized; it drives the HTTP response status code.
type APIError struct {
	HTTPStatus int               `json:"-"`
	ErrCode    Code              `json:"code"`
	Message    string            `json:"message"`
	Fields     map[string]string `json:"fields,omitempty"`
	cause      error
}

func (e *APIError) Error() string {
	return string(e.ErrCode) + ": " + e.Message
}

func (e *APIError) Unwrap() error { return e.cause }

func New(status int, code Code, message string) *APIError {
	return &APIError{HTTPStatus: status, ErrCode: code, Message: message}
}

func Wrap(status int, code Code, message string, cause error) *APIError {
	return &APIError{HTTPStatus: status, ErrCode: code, Message: message, cause: cause}
}

func WithField(err *APIError, field, detail string) *APIError {
	clone := *err
	if clone.Fields == nil {
		clone.Fields = map[string]string{}
	}
	clone.Fields[field] = detail
	return &clone
}

var (
	ErrValidation        = New(http.StatusBadRequest, CodeValidation, "The request could not be validated.")
	ErrUnauthenticated   = New(http.StatusUnauthorized, CodeUnauthenticated, "Authentication is required.")
	ErrForbidden         = New(http.StatusForbidden, CodeForbidden, "You do not have permission to perform this action.")
	ErrNotFound          = New(http.StatusNotFound, CodeNotFound, "The requested resource was not found.")
	ErrConflict          = New(http.StatusConflict, CodeConflict, "The request conflicts with existing state.")
	ErrStepUpRequired    = New(http.StatusForbidden, CodeStepUpRequired, "This action requires re-authentication.")
	ErrEntitlementDenied = New(http.StatusForbidden, CodeEntitlementDenied, "Your subscription does not include this capability.")
	ErrInternal          = New(http.StatusInternalServerError, CodeInternal, "An internal error occurred.")
)

// errorDetail walks the Unwrap chain and joins every level's message, so a
// wrapped *APIError's underlying cause (e.g. a database error) is visible in
// server logs even though APIError.Error() intentionally only returns the
// client-safe "CODE: message" summary.
func errorDetail(err error) string {
	var parts []string
	for err != nil {
		parts = append(parts, err.Error())
		err = errors.Unwrap(err)
	}
	detail := ""
	for i, p := range parts {
		if i > 0 {
			detail += " <- "
		}
		detail += p
	}
	return detail
}

// WriteJSON writes err as a structured JSON response. Any error that is not
// an *APIError is logged with full detail server-side and returned to the
// client only as a generic internal error — never leaking internals.
func WriteJSON(w http.ResponseWriter, r *http.Request, logger *slog.Logger, err error) {
	var apiErr *APIError
	if !errors.As(err, &apiErr) {
		logger.ErrorContext(r.Context(), "unhandled error", "error", err.Error(), "path", r.URL.Path)
		apiErr = ErrInternal
	} else if apiErr.HTTPStatus >= 500 {
		// apiErr.Error() alone only prints "CODE: message" -- log the full
		// wrapped cause chain (via %v on the original err) so the operator
		// can actually diagnose the failure without exposing it to the client.
		logger.ErrorContext(r.Context(), "internal error", "error", err.Error(), "detail", errorDetail(err), "path", r.URL.Path)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(apiErr.HTTPStatus)
	_ = json.NewEncoder(w).Encode(struct {
		Error *APIError `json:"error"`
	}{Error: apiErr})
}
