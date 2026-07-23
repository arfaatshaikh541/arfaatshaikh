package artefacts

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"

	"gridkeep/control-api/internal/platform/apierror"
)

type Handlers struct {
	svc    *Service
	logger *slog.Logger
}

func NewHandlers(svc *Service, logger *slog.Logger) *Handlers {
	return &Handlers{svc: svc, logger: logger}
}

func decodeJSON(r *http.Request, dst any) error {
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	return dec.Decode(dst)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeServiceError(w http.ResponseWriter, r *http.Request, logger *slog.Logger, err error) {
	switch {
	case errors.Is(err, ErrNotFound):
		apierror.WriteJSON(w, r, logger, apierror.ErrNotFound)
	case errors.Is(err, ErrNotPending), errors.Is(err, ErrNotAvailable):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusConflict, apierror.CodeConflict, err.Error()))
	case errors.Is(err, ErrInfected):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusForbidden, apierror.CodeForbidden, err.Error()))
	case errors.Is(err, ErrContentTooLarge), errors.Is(err, ErrContentTypeNotAllowed):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusBadRequest, apierror.CodeValidation, err.Error()))
	case errors.Is(err, ErrUploadNotFoundInStorage), errors.Is(err, ErrSizeMismatch), errors.Is(err, ErrChecksumMismatch):
		apierror.WriteJSON(w, r, logger, apierror.New(http.StatusUnprocessableEntity, apierror.CodeValidation, err.Error()))
	default:
		apierror.WriteJSON(w, r, logger, apierror.Wrap(500, apierror.CodeInternal, "artefact operation failed", err))
	}
}

type authoriseUploadRequest struct {
	Purpose       string `json:"purpose"`
	ContentType   string `json:"content_type"`
	ContentLength int64  `json:"content_length"`
}

type authoriseUploadResponse struct {
	Upload    Upload `json:"upload"`
	UploadURL string `json:"upload_url"`
}

func (h *Handlers) AuthoriseUpload(w http.ResponseWriter, r *http.Request) {
	var req authoriseUploadRequest
	if err := decodeJSON(r, &req); err != nil || req.Purpose == "" || req.ContentType == "" {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	upload, uploadURL, err := h.svc.AuthoriseUpload(r.Context(), req.Purpose, req.ContentType, req.ContentLength)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusCreated, authoriseUploadResponse{Upload: upload, UploadURL: uploadURL})
}

type completeUploadRequest struct {
	ChecksumSHA256 string `json:"checksum_sha256"`
}

func (h *Handlers) CompleteUpload(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "artefactID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req completeUploadRequest
	if err := decodeJSON(r, &req); err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	upload, err := h.svc.CompleteUpload(r.Context(), id, req.ChecksumSHA256)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, upload)
}

func (h *Handlers) ListArtefacts(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.ListArtefacts(r.Context())
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.Wrap(500, apierror.CodeInternal, "failed to list artefacts", err))
		return
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *Handlers) GetArtefact(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "artefactID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	u, err := h.svc.GetArtefact(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, u)
}

func (h *Handlers) RequestDownload(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "artefactID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	url, err := h.svc.RequestDownload(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"download_url": url})
}

func (h *Handlers) DeleteArtefact(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "artefactID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	u, err := h.svc.DeleteArtefact(r.Context(), id)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, u)
}

type malwareScanResultRequest struct {
	Result string `json:"result"`
}

func (h *Handlers) MarkMalwareScanResult(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(chi.URLParam(r, "artefactID"))
	if err != nil {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	var req malwareScanResultRequest
	if err := decodeJSON(r, &req); err != nil || (req.Result != "clean" && req.Result != "infected" && req.Result != "error") {
		apierror.WriteJSON(w, r, h.logger, apierror.ErrValidation)
		return
	}
	u, err := h.svc.MarkMalwareScanResult(r.Context(), id, req.Result)
	if err != nil {
		writeServiceError(w, r, h.logger, err)
		return
	}
	writeJSON(w, http.StatusOK, u)
}
