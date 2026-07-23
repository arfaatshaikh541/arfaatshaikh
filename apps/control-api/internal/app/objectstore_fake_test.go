package app_test

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"sync"
	"testing"
	"time"

	"gridkeep/control-api/internal/platform/storage"
)

// fakeObjectStore is a TEST-ONLY double for artefacts.ObjectStore backed by
// a real httptest.Server (not just an in-memory stub returning canned
// values) -- a test's presigned PUT/GET URLs are real HTTP endpoints an
// http.Client actually uploads to and downloads from, so
// internal/modules/artefacts' completion-time Stat/hash-verification logic
// runs against genuinely-stored bytes, exactly as it would against a live
// MinIO instance. Live MinIO connectivity itself could not be exercised in
// this sandboxed session (see internal/platform/storage's commit message);
// this fake exists so the artefact upload/download workflow still has real
// integration-test coverage in the meantime.
type fakeObjectStore struct {
	srv *httptest.Server

	mu      sync.Mutex
	objects map[string][]byte
}

func startFakeObjectStore(t *testing.T) *fakeObjectStore {
	t.Helper()
	fos := &fakeObjectStore{objects: map[string][]byte{}}
	mux := http.NewServeMux()
	mux.HandleFunc("/put/", func(w http.ResponseWriter, r *http.Request) {
		key, err := url.QueryUnescape(r.URL.Path[len("/put/"):])
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		fos.mu.Lock()
		fos.objects[key] = body
		fos.mu.Unlock()
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("/get/", func(w http.ResponseWriter, r *http.Request) {
		key, err := url.QueryUnescape(r.URL.Path[len("/get/"):])
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		fos.mu.Lock()
		body, ok := fos.objects[key]
		fos.mu.Unlock()
		if !ok {
			http.Error(w, "not found", http.StatusNotFound)
			return
		}
		_, _ = w.Write(body)
	})
	fos.srv = httptest.NewServer(mux)
	t.Cleanup(fos.srv.Close)
	return fos
}

func (f *fakeObjectStore) Bucket() string { return "test-bucket" }

func (f *fakeObjectStore) PresignedPutURL(_ context.Context, objectKey string, _ time.Duration) (string, error) {
	return f.srv.URL + "/put/" + url.QueryEscape(objectKey), nil
}

func (f *fakeObjectStore) PresignedGetURL(_ context.Context, objectKey string, _ time.Duration) (string, error) {
	return f.srv.URL + "/get/" + url.QueryEscape(objectKey), nil
}

func (f *fakeObjectStore) Stat(_ context.Context, objectKey string) (storage.ObjectInfo, error) {
	f.mu.Lock()
	body, ok := f.objects[objectKey]
	f.mu.Unlock()
	if !ok {
		return storage.ObjectInfo{}, fmt.Errorf("object %q not found", objectKey)
	}
	versionBytes := make([]byte, 8)
	_, _ = rand.Read(versionBytes)
	return storage.ObjectInfo{
		Size:        int64(len(body)),
		ContentType: "application/octet-stream",
		ETag:        "fake-etag",
		VersionID:   hex.EncodeToString(versionBytes),
	}, nil
}

func (f *fakeObjectStore) Get(_ context.Context, objectKey string) (io.ReadCloser, error) {
	f.mu.Lock()
	body, ok := f.objects[objectKey]
	f.mu.Unlock()
	if !ok {
		return nil, fmt.Errorf("object %q not found", objectKey)
	}
	return io.NopCloser(bytes.NewReader(body)), nil
}

func (f *fakeObjectStore) Remove(_ context.Context, objectKey string) error {
	f.mu.Lock()
	delete(f.objects, objectKey)
	f.mu.Unlock()
	return nil
}

// putObject uploads content to a presigned PUT URL exactly like a real
// browser/CLI would -- tests use this to simulate "the client already
// uploaded the bytes" before calling the complete-upload endpoint.
func putObject(t *testing.T, uploadURL string, content []byte) {
	t.Helper()
	req, err := http.NewRequest(http.MethodPut, uploadURL, bytes.NewReader(content))
	if err != nil {
		t.Fatalf("build put request: %v", err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("put object: %v", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("put object: expected 200, got %d", resp.StatusCode)
	}
}
