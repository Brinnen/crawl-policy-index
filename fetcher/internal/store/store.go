package store

import (
	"bufio"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

type Observation struct {
	PanelVersion             string  `json:"panel_version"`
	RunDate                  string  `json:"run_date"`
	Domain                   string  `json:"domain"`
	Resource                 string  `json:"resource"`
	FetchedAt                string  `json:"fetched_at"`
	URLRequested             string  `json:"url_requested"`
	URLFinal                 string  `json:"url_final,omitempty"`
	RedirectCount            int     `json:"redirect_count"`
	CrossedRegistrableDomain bool    `json:"crossed_registrable_domain"`
	SchemeUsed               string  `json:"scheme_used,omitempty"`
	HTTPStatus               *int    `json:"http_status"`
	Outcome                  string  `json:"outcome"`
	ContentSHA256            string  `json:"content_sha256,omitempty"`
	ContentLength            int     `json:"content_length"`
	ContentType              string  `json:"content_type,omitempty"`
	ContentEncoding          string  `json:"content_encoding,omitempty"`
	Truncated                bool    `json:"truncated"`
	LatencyMS                int     `json:"latency_ms"`
	BlobWritten              bool    `json:"blob_written"`
	FetcherVersion           string  `json:"fetcher_version"`
	ErrorDetail              *string `json:"error_detail"`
}

type FS struct {
	root string
	mu   sync.Mutex
	obs  map[string]*os.File
}

func NewFS(root string) *FS {
	return &FS{root: root, obs: map[string]*os.File{}}
}

func (s *FS) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	var first error
	for k, f := range s.obs {
		if err := f.Close(); err != nil && first == nil {
			first = err
		}
		delete(s.obs, k)
	}
	return first
}

func SHA256(body []byte) string {
	sum := sha256.Sum256(body)
	return hex.EncodeToString(sum[:])
}

func (s *FS) HasBlob(sha string) bool {
	_, err := os.Stat(s.blobPath(sha))
	return err == nil
}

func (s *FS) PutBlob(sha string, body []byte) (bool, error) {
	path := s.blobPath(sha)
	if _, err := os.Stat(path); err == nil {
		return false, nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return false, err
	}
	tmp := path + ".tmp"
	f, err := os.Create(tmp)
	if err != nil {
		return false, err
	}
	zw := gzip.NewWriter(f)
	if _, err := zw.Write(body); err != nil {
		_ = f.Close()
		_ = os.Remove(tmp)
		return false, err
	}
	if err := zw.Close(); err != nil {
		_ = f.Close()
		_ = os.Remove(tmp)
		return false, err
	}
	if err := f.Close(); err != nil {
		_ = os.Remove(tmp)
		return false, err
	}
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp)
		return false, err
	}
	return true, nil
}

func (s *FS) blobPath(sha string) string {
	if len(sha) < 4 {
		sha = sha + "0000"
	}
	return filepath.Join(s.root, "blob", sha[0:2], sha[2:4], sha+".gz")
}

func (s *FS) WriteObservation(shard int, obs Observation) error {
	dir := filepath.Join(s.root, "obs", "dt="+obs.RunDate, "resource="+obs.Resource)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	key := fmt.Sprintf("%s|%s|%d", obs.RunDate, obs.Resource, shard)
	s.mu.Lock()
	f, ok := s.obs[key]
	if !ok {
		path := filepath.Join(dir, fmt.Sprintf("part-%d-0.ndjson", shard))
		var err error
		f, err = os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
		if err != nil {
			s.mu.Unlock()
			return err
		}
		s.obs[key] = f
	}
	enc := json.NewEncoder(f)
	err := enc.Encode(obs)
	s.mu.Unlock()
	return err
}

func (s *FS) LoadCompleted(runDate string) (map[string]struct{}, error) {
	done := map[string]struct{}{}
	root := filepath.Join(s.root, "obs", "dt="+runDate)
	_ = filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || !strings.HasSuffix(path, ".ndjson") {
			return nil
		}
		f, err := os.Open(path)
		if err != nil {
			return nil
		}
		defer f.Close()
		sc := bufio.NewScanner(f)
		sc.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
		for sc.Scan() {
			var obs Observation
			if json.Unmarshal(sc.Bytes(), &obs) != nil {
				continue
			}
			done[obs.Domain+"|"+obs.Resource] = struct{}{}
		}
		return nil
	})
	return done, nil
}

type Manifest struct {
	RunDate                 string         `json:"run_date"`
	PanelVersion            string         `json:"panel_version"`
	FetcherVersion          string         `json:"fetcher_version"`
	StartedAt               string         `json:"started_at"`
	FinishedAt              string         `json:"finished_at"`
	DomainsInPanel          int            `json:"domains_in_panel"`
	Attempted               int            `json:"attempted"`
	ByOutcome               map[string]int `json:"by_outcome"`
	BlobsWritten            int            `json:"blobs_written"`
	UnexplainedFailureRate  float64        `json:"unexplained_failure_rate"`
	Complete                bool           `json:"complete"`
}

func (s *FS) WriteManifest(m Manifest) error {
	dir := filepath.Join(s.root, "obs", "manifest")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	path := filepath.Join(dir, m.RunDate+".json")
	b, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(b, '\n'), 0o644)
}

func NowUTC() string {
	return time.Now().UTC().Format(time.RFC3339Nano)
}

func RunDateUTC() string {
	return time.Now().UTC().Format("2006-01-02")
}
