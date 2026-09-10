package fetch

import (
	"bytes"
	"compress/gzip"
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/crawl-policy-index/fetcher/internal/config"
	"github.com/crawl-policy-index/fetcher/internal/store"
)

func testCfg(base string, root string) config.Config {
	return config.Config{
		Panel:   config.PanelConfig{Version: "dev"},
		Storage: config.StorageConfig{Backend: "fs", Root: root},
		Fetcher: config.FetcherConfig{
			Resources:        []string{"robots_txt"},
			Shards:           1,
			WorkersPerShard:  4,
			GlobalRateLimit:  1000,
			PerHostInflight:  1,
			PerIPConcurrent:  4,
			MaxRedirects:     3,
			UserAgent:        "CrawlPolicyIndex/1.0 (+https://crawlpolicyindex.org/bot)",
			FetcherVersion:   "test",
			ForceBaseURL:     base,
			RetryBackoffZero: true,
			Retry:            config.RetryConfig{Attempts: 1, BackoffS: []float64{0}},
			Timeouts:         config.Timeouts{ConnectS: 2, TLSS: 2, TotalS: 3},
			SizeCapsBytes: map[string]int{
				"robots_txt":  1024,
				"llms_txt":    1024,
				"sitemap_xml": 1024,
			},
		},
	}
}

func newFetcher(t *testing.T, handler http.Handler) (*Fetcher, *httptest.Server, *store.FS) {
	t.Helper()
	srv := httptest.NewServer(handler)
	t.Cleanup(srv.Close)
	root := t.TempDir()
	st := store.NewFS(root)
	t.Cleanup(func() { _ = st.Close() })
	cfg := testCfg(srv.URL, root)
	return New(cfg, st), srv, st
}

func TestOutcomeOK(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/robots.txt" {
			t.Errorf("path %s", r.URL.Path)
		}
		if !strings.Contains(r.Header.Get("User-Agent"), "CrawlPolicyIndex") {
			t.Errorf("ua %s", r.Header.Get("User-Agent"))
		}
		w.Header().Set("Content-Type", "text/plain")
		_, _ = w.Write([]byte("User-agent: *\nDisallow: /admin\n"))
	}))
	obs, err := f.Fetch(context.Background(), "example.com", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if obs.Outcome != OutcomeOK {
		t.Fatalf("outcome %s", obs.Outcome)
	}
	if !obs.BlobWritten {
		t.Fatal("expected blob write")
	}
	if obs.ContentSHA256 == "" {
		t.Fatal("missing hash")
	}
}

func TestOutcomeNotFound(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(404)
	}))
	assertOutcome(t, f, OutcomeNotFound)
}

func TestOutcomeForbidden(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(403)
	}))
	assertOutcome(t, f, OutcomeForbidden)
}

func TestOutcomeServerError(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
	}))
	assertOutcome(t, f, OutcomeServerError)
}

func TestOutcomeRateLimited(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(429)
	}))
	assertOutcome(t, f, OutcomeRateLimited)
}

func TestOutcomeEmptyBody(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
	}))
	assertOutcome(t, f, OutcomeEmptyBody)
}

func TestOutcomeRedirectLoop(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/robots.txt", http.StatusFound)
	}))
	assertOutcome(t, f, OutcomeRedirectLoop)
}

func TestOutcomeTooLargeGzipBomb(t *testing.T) {
	var buf bytes.Buffer
	zw := gzip.NewWriter(&buf)
	_, _ = zw.Write(bytes.Repeat([]byte("A"), 20_000))
	_ = zw.Close()
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Encoding", "gzip")
		w.Header().Set("Content-Type", "text/plain")
		_, _ = w.Write(buf.Bytes())
	}))
	obs, err := f.Fetch(context.Background(), "example.com", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if obs.Outcome != OutcomeTooLarge {
		t.Fatalf("got %s", obs.Outcome)
	}
}

func TestOutcomeTimeout(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(4 * time.Second)
		_, _ = w.Write([]byte("late"))
	}))
	assertOutcome(t, f, OutcomeTimeout)
}

func TestOutcomeDNS(t *testing.T) {
	root := t.TempDir()
	st := store.NewFS(root)
	cfg := testCfg("", root)
	cfg.Fetcher.ForceBaseURL = ""
	f := New(cfg, st)
	obs, err := f.Fetch(context.Background(), "this-host-does-not-exist-xyz.invalid", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if obs.Outcome != OutcomeDNS && obs.Outcome != OutcomeTimeout {
		t.Fatalf("got %s", obs.Outcome)
	}
}

func TestOutcomeConnRefused(t *testing.T) {
	root := t.TempDir()
	st := store.NewFS(root)
	cfg := testCfg("http://127.0.0.1:1", root)
	f := New(cfg, st)
	obs, err := f.Fetch(context.Background(), "example.com", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if obs.Outcome != OutcomeConnRefused && obs.Outcome != OutcomeTimeout {
		t.Fatalf("got %s", obs.Outcome)
	}
}

func TestOutcomeTLS(t *testing.T) {
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("ok"))
	}))
	t.Cleanup(srv.Close)
	root := t.TempDir()
	st := store.NewFS(root)
	cfg := testCfg(srv.URL, root)
	f := New(cfg, st)
	obs, err := f.Fetch(context.Background(), "example.com", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if obs.Outcome != OutcomeTLS && obs.Outcome != OutcomeTimeout {
		t.Fatalf("got %s detail=%v", obs.Outcome, obs.ErrorDetail)
	}
}

func TestOutcomeInvalidURL(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	obs, err := f.Fetch(context.Background(), "bad domain", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if obs.Outcome != OutcomeInvalidURL {
		t.Fatalf("got %s", obs.Outcome)
	}
}

func TestSecondFetchDoesNotRewriteBlob(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("User-agent: *\nDisallow:\n"))
	}))
	obs1, err := f.Fetch(context.Background(), "example.com", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	obs2, err := f.Fetch(context.Background(), "example.com", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if !obs1.BlobWritten || obs2.BlobWritten {
		t.Fatalf("blob_written %v then %v", obs1.BlobWritten, obs2.BlobWritten)
	}
}

func TestOneInflightPerHost(t *testing.T) {
	var inflight atomic.Int32
	var max atomic.Int32
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := inflight.Add(1)
		for {
			cur := max.Load()
			if n <= cur || max.CompareAndSwap(cur, n) {
				break
			}
		}
		time.Sleep(50 * time.Millisecond)
		inflight.Add(-1)
		_, _ = w.Write([]byte("User-agent: *\nDisallow:\n"))
	}))
	ctx := context.Background()
	errCh := make(chan error, 8)
	for i := 0; i < 8; i++ {
		go func() {
			_, err := f.Fetch(ctx, "example.com", "robots_txt", "2026-09-08", "dev")
			errCh <- err
		}()
	}
	for i := 0; i < 8; i++ {
		if err := <-errCh; err != nil {
			t.Fatal(err)
		}
	}
	if max.Load() > 1 {
		t.Fatalf("max inflight %d", max.Load())
	}
}

func TestResumeSkipsRecordedPairs(t *testing.T) {
	f, _, st := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("ok body"))
	}))
	obs, err := f.Fetch(context.Background(), "example.com", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if err := st.WriteObservation(0, obs); err != nil {
		t.Fatal(err)
	}
	done, err := st.LoadCompleted("2026-09-08")
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := done["example.com|robots_txt"]; !ok {
		t.Fatal("expected recorded pair")
	}
}

func TestAllOutcomesListed(t *testing.T) {
	if len(AllOutcomes) != 13 {
		t.Fatalf("want 13 outcomes, got %d", len(AllOutcomes))
	}
}

func assertOutcome(t *testing.T, f *Fetcher, want string) {
	t.Helper()
	obs, err := f.Fetch(context.Background(), "example.com", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if obs.Outcome != want {
		t.Fatalf("want %s got %s detail=%v", want, obs.Outcome, obs.ErrorDetail)
	}
}

func TestTruncatedKeepsPrefix(t *testing.T) {
	f, _, _ := newFetcher(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write(bytes.Repeat([]byte("x"), 5000))
	}))
	obs, err := f.Fetch(context.Background(), "example.com", "robots_txt", "2026-09-08", "dev")
	if err != nil {
		t.Fatal(err)
	}
	if obs.Outcome != OutcomeOK {
		t.Fatalf("got %s", obs.Outcome)
	}
	if !obs.Truncated {
		t.Fatal("expected truncated")
	}
	if obs.ContentLength != 1024 {
		t.Fatalf("len %d", obs.ContentLength)
	}
}
