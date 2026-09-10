package fetch

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"syscall"
	"time"

	"golang.org/x/net/publicsuffix"

	"github.com/crawl-policy-index/fetcher/internal/config"
	"github.com/crawl-policy-index/fetcher/internal/panel"
	"github.com/crawl-policy-index/fetcher/internal/store"
)

const (
	OutcomeOK           = "ok"
	OutcomeNotFound     = "not_found"
	OutcomeForbidden    = "forbidden"
	OutcomeServerError  = "server_error"
	OutcomeRateLimited  = "rate_limited"
	OutcomeTimeout      = "timeout"
	OutcomeDNS          = "dns_error"
	OutcomeTLS          = "tls_error"
	OutcomeConnRefused  = "conn_refused"
	OutcomeTooLarge     = "too_large"
	OutcomeEmptyBody    = "empty_body"
	OutcomeRedirectLoop = "redirect_loop"
	OutcomeInvalidURL   = "invalid_url"
)

var AllOutcomes = []string{
	OutcomeOK, OutcomeNotFound, OutcomeForbidden, OutcomeServerError,
	OutcomeRateLimited, OutcomeTimeout, OutcomeDNS, OutcomeTLS,
	OutcomeConnRefused, OutcomeTooLarge, OutcomeEmptyBody,
	OutcomeRedirectLoop, OutcomeInvalidURL,
}

type Fetcher struct {
	cfg     config.Config
	client  *http.Client
	limits  *Limits
	store   *store.FS
}

func New(cfg config.Config, st *store.FS) *Fetcher {
	timeouts := cfg.Fetcher.Timeouts
	total := time.Duration(timeouts.TotalS) * time.Second
	if total == 0 {
		total = 15 * time.Second
	}
	connect := time.Duration(timeouts.ConnectS) * time.Second
	if connect == 0 {
		connect = 5 * time.Second
	}
	tlsTO := time.Duration(timeouts.TLSS) * time.Second
	if tlsTO == 0 {
		tlsTO = 10 * time.Second
	}
	dialer := &net.Dialer{Timeout: connect}
	transport := &http.Transport{
		Proxy:                 http.ProxyFromEnvironment,
		DialContext:           dialer.DialContext,
		ForceAttemptHTTP2:     true,
		MaxIdleConns:          256,
		IdleConnTimeout:       30 * time.Second,
		TLSHandshakeTimeout:   tlsTO,
		ExpectContinueTimeout: 1 * time.Second,
		DisableCompression:    true,
	}
	maxRedir := cfg.Fetcher.MaxRedirects
	client := &http.Client{
		Transport: transport,
		Timeout:   total,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if len(via) >= maxRedir {
				return fmt.Errorf("%w", errRedirectLoop)
			}
			return nil
		},
	}
	return &Fetcher{
		cfg:    cfg,
		client: client,
		limits: NewLimits(cfg.Fetcher.PerHostInflight, cfg.Fetcher.PerIPConcurrent, cfg.Fetcher.GlobalRateLimit),
		store:  st,
	}
}

var errRedirectLoop = errors.New("redirect loop")

type result struct {
	obs  store.Observation
	body []byte
}

func (f *Fetcher) Fetch(ctx context.Context, domain, resource, runDate, panelVersion string) (store.Observation, error) {
	return f.FetchAt(ctx, domain, resource, runDate, panelVersion, "")
}

func (f *Fetcher) FetchAt(ctx context.Context, domain, resource, runDate, panelVersion, targetURL string) (store.Observation, error) {
	path := panel.ResourcePath(resource)
	capBytes := f.cfg.Fetcher.SizeCapsBytes[resource]
	if capBytes == 0 {
		capBytes = 1 << 20
	}

	obs := store.Observation{
		PanelVersion:   panelVersion,
		RunDate:        runDate,
		Domain:         domain,
		Resource:       resource,
		FetchedAt:      store.NowUTC(),
		FetcherVersion: f.cfg.Fetcher.FetcherVersion,
	}

	if strings.TrimSpace(domain) == "" || strings.ContainsAny(domain, " \t\n") {
		obs.Outcome = OutcomeInvalidURL
		msg := "invalid domain"
		obs.ErrorDetail = &msg
		return obs, nil
	}

	httpsURL, httpURL := f.targetURLs(domain, path, targetURL)

	start := time.Now()
	res, err := f.attempt(ctx, domain, httpsURL, capBytes, "https")
	if err != nil && shouldFallbackHTTP(err) && f.cfg.Fetcher.ForceBaseURL == "" {
		res, err = f.attempt(ctx, domain, httpURL, capBytes, "http")
	}
	obs.LatencyMS = int(time.Since(start).Milliseconds())
	if res != nil {
		obs = merge(obs, res.obs)
		if res.body != nil && (obs.Outcome == OutcomeOK) {
			sha := store.SHA256(res.body)
			obs.ContentSHA256 = sha
			obs.ContentLength = len(res.body)
			written, werr := f.store.PutBlob(sha, res.body)
			if werr != nil {
				return obs, werr
			}
			obs.BlobWritten = written
		}
		return obs, nil
	}
	obs.Outcome, obs.ErrorDetail = classifyNetErr(err)
	return obs, nil
}

func (f *Fetcher) targetURLs(domain, path, override string) (httpsURL, httpURL string) {
	base := strings.TrimRight(f.cfg.Fetcher.ForceBaseURL, "/")
	if override != "" {
		if base != "" {
			u, err := url.Parse(override)
			p := path
			if err == nil && u.Path != "" {
				p = u.Path
			}
			return base + p, base + p
		}
		httpsURL = override
		httpURL = override
		if strings.HasPrefix(override, "https://") {
			httpURL = "http://" + strings.TrimPrefix(override, "https://")
		}
		return httpsURL, httpURL
	}
	httpsURL = "https://" + domain + path
	httpURL = "http://" + domain + path
	if base != "" {
		httpsURL = base + path
		httpURL = base + path
	}
	return httpsURL, httpURL
}

func merge(base store.Observation, over store.Observation) store.Observation {
	base.URLRequested = over.URLRequested
	base.URLFinal = over.URLFinal
	base.RedirectCount = over.RedirectCount
	base.CrossedRegistrableDomain = over.CrossedRegistrableDomain
	base.SchemeUsed = over.SchemeUsed
	base.HTTPStatus = over.HTTPStatus
	base.Outcome = over.Outcome
	base.ContentType = over.ContentType
	base.ContentEncoding = over.ContentEncoding
	base.Truncated = over.Truncated
	base.ErrorDetail = over.ErrorDetail
	base.ContentLength = over.ContentLength
	base.ContentSHA256 = over.ContentSHA256
	return base
}

func (f *Fetcher) attempt(ctx context.Context, domain, rawURL string, capBytes int, scheme string) (*result, error) {
	u, err := url.Parse(rawURL)
	if err != nil {
		msg := err.Error()
		return &result{obs: store.Observation{
			URLRequested: rawURL,
			SchemeUsed:   scheme,
			Outcome:      OutcomeInvalidURL,
			ErrorDetail:  &msg,
		}}, nil
	}

	host := u.Hostname()
	ip := host
	if addrs, err := net.DefaultResolver.LookupIPAddr(ctx, host); err == nil && len(addrs) > 0 {
		ip = addrs[0].IP.String()
	}

	release, err := f.limits.Acquire(ctx, host, ip)
	if err != nil {
		return nil, err
	}
	defer release()

	tries := 1 + f.cfg.Fetcher.Retry.Attempts
	if tries < 1 {
		tries = 1
	}
	var last *result
	var lastErr error
	for i := 0; i < tries; i++ {
		if i > 0 {
			if err := f.backoff(ctx); err != nil {
				return nil, err
			}
		}
		last, lastErr = f.doOnce(ctx, domain, u, capBytes, scheme)
		if lastErr == nil && last != nil && !retryable(last.obs.Outcome) {
			return last, nil
		}
		if lastErr != nil && !retryableErr(lastErr) {
			return nil, lastErr
		}
	}
	if last != nil {
		return last, nil
	}
	return nil, lastErr
}

func (f *Fetcher) backoff(ctx context.Context) error {
	if f.cfg.Fetcher.RetryBackoffZero {
		return nil
	}
	d := 30 * time.Second
	if len(f.cfg.Fetcher.Retry.BackoffS) > 0 {
		d = time.Duration(f.cfg.Fetcher.Retry.BackoffS[0] * float64(time.Second))
	}
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

func retryable(outcome string) bool {
	return outcome == OutcomeRateLimited || outcome == OutcomeServerError ||
		outcome == OutcomeTimeout || outcome == OutcomeDNS ||
		outcome == OutcomeTLS || outcome == OutcomeConnRefused
}

func retryableErr(err error) bool {
	o, _ := classifyNetErr(err)
	return retryable(o)
}

func (f *Fetcher) doOnce(ctx context.Context, domain string, u *url.URL, capBytes int, scheme string) (*result, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		msg := err.Error()
		return &result{obs: store.Observation{URLRequested: u.String(), Outcome: OutcomeInvalidURL, ErrorDetail: &msg, SchemeUsed: scheme}}, nil
	}
	req.Header.Set("User-Agent", f.cfg.Fetcher.UserAgent)
	req.Header.Set("Accept", "text/plain, text/markdown, application/xml, */*")
	req.Header.Set("Accept-Encoding", "gzip")
	if f.cfg.Fetcher.ForceBaseURL != "" {
		req.Host = domain
	}

	resp, err := f.client.Do(req)
	if err != nil {
		if errors.Is(err, errRedirectLoop) || strings.Contains(err.Error(), "redirect loop") {
			st := 302
			return &result{obs: store.Observation{
				URLRequested: u.String(),
				SchemeUsed:   scheme,
				HTTPStatus:   &st,
				Outcome:      OutcomeRedirectLoop,
			}}, nil
		}
		return nil, err
	}
	defer resp.Body.Close()

	obs := store.Observation{
		URLRequested:  u.String(),
		URLFinal:      resp.Request.URL.String(),
		SchemeUsed:    resp.Request.URL.Scheme,
		HTTPStatus:    intPtr(resp.StatusCode),
		ContentType:   resp.Header.Get("Content-Type"),
		ContentEncoding: resp.Header.Get("Content-Encoding"),
	}
	if obs.SchemeUsed == "" {
		obs.SchemeUsed = scheme
	}
	obs.RedirectCount = redirectCount(u.String(), resp.Request.URL.String(), resp.Header)
	obs.CrossedRegistrableDomain = crossedRegDomain(domain, resp.Request.URL.Hostname())

	limited := io.LimitReader(resp.Body, int64(capBytes)+1)
	raw, err := io.ReadAll(limited)
	if err != nil {
		return nil, err
	}
	truncated := false
	if len(raw) > capBytes {
		raw = raw[:capBytes]
		truncated = true
	}

	body := raw
	enc := strings.ToLower(resp.Header.Get("Content-Encoding"))
	if strings.Contains(enc, "gzip") || (len(raw) >= 2 && raw[0] == 0x1f && raw[1] == 0x8b) {
		gr, gerr := gzip.NewReader(bytes.NewReader(raw))
		if gerr == nil {
			decomp, derr := io.ReadAll(io.LimitReader(gr, int64(capBytes)*4+1))
			_ = gr.Close()
			if derr != nil && !errors.Is(derr, io.EOF) && !errors.Is(derr, io.ErrUnexpectedEOF) {
				return nil, derr
			}
			if len(decomp) > capBytes*4 {
				obs.Outcome = OutcomeTooLarge
				obs.Truncated = true
				msg := "decompressed body exceeded 4x cap"
				obs.ErrorDetail = &msg
				return &result{obs: obs}, nil
			}
			body = decomp
		}
	}

	obs.Truncated = truncated
	obs.ContentLength = len(body)
	obs.Outcome = statusOutcome(resp.StatusCode, len(body), truncated)
	if truncated && obs.Outcome == OutcomeOK {
		obs.Truncated = true
	}
	if obs.Outcome == OutcomeTooLarge {
		return &result{obs: obs}, nil
	}
	if obs.Outcome != OutcomeOK {
		return &result{obs: obs}, nil
	}
	return &result{obs: obs, body: body}, nil
}

func statusOutcome(code, bodyLen int, truncated bool) string {
	if truncated && bodyLen > 0 && code >= 200 && code < 300 {
		// kept first N bytes; still a successful fetch
	}
	switch {
	case code == 404 || code == 410:
		return OutcomeNotFound
	case code == 401 || code == 403 || (code >= 400 && code < 500 && code != 429):
		if code == 408 {
			return OutcomeTimeout
		}
		return OutcomeForbidden
	case code == 429:
		return OutcomeRateLimited
	case code >= 500:
		return OutcomeServerError
	case code >= 200 && code < 300:
		if bodyLen == 0 {
			return OutcomeEmptyBody
		}
		return OutcomeOK
	default:
		return OutcomeServerError
	}
}

func classifyNetErr(err error) (string, *string) {
	if err == nil {
		return OutcomeOK, nil
	}
	msg := err.Error()
	detail := &msg
	if errors.Is(err, context.DeadlineExceeded) || osTimeout(err) {
		return OutcomeTimeout, detail
	}
	var dnsErr *net.DNSError
	if errors.As(err, &dnsErr) {
		return OutcomeDNS, detail
	}
	var tlsErr *tls.CertificateVerificationError
	if errors.As(err, &tlsErr) || strings.Contains(msg, "tls:") || strings.Contains(msg, "certificate") || strings.Contains(msg, "handshake") {
		return OutcomeTLS, detail
	}
	var opErr *net.OpError
	if errors.As(err, &opErr) {
		if errors.Is(opErr.Err, syscall.ECONNREFUSED) || strings.Contains(opErr.Err.Error(), "refused") {
			return OutcomeConnRefused, detail
		}
		if opErr.Timeout() {
			return OutcomeTimeout, detail
		}
	}
	if errors.Is(err, syscall.ECONNREFUSED) || strings.Contains(msg, "connection refused") {
		return OutcomeConnRefused, detail
	}
	if strings.Contains(msg, "no such host") {
		return OutcomeDNS, detail
	}
	return OutcomeTimeout, detail
}

func osTimeout(err error) bool {
	var t interface{ Timeout() bool }
	return errors.As(err, &t) && t.Timeout()
}

func shouldFallbackHTTP(err error) bool {
	o, _ := classifyNetErr(err)
	return o == OutcomeTLS || o == OutcomeConnRefused || o == OutcomeTimeout
}

func crossedRegDomain(requestedHost, finalHost string) bool {
	if finalHost == "" || requestedHost == "" {
		return false
	}
	a, err1 := publicsuffix.EffectiveTLDPlusOne(strings.ToLower(requestedHost))
	b, err2 := publicsuffix.EffectiveTLDPlusOne(strings.ToLower(finalHost))
	if err1 != nil || err2 != nil {
		return !strings.EqualFold(requestedHost, finalHost)
	}
	return a != b
}

func redirectCount(requested, final string, header http.Header) int {
	if requested == final {
		return 0
	}
	// Client follows redirects; we cannot see every hop cheaply.
	// Count at least 1 when the final URL differs.
	if header.Get("Location") != "" {
		return 1
	}
	if requested != final {
		return 1
	}
	return 0
}

func intPtr(v int) *int { return &v }
