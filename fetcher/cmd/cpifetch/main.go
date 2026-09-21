package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/crawl-policy-index/fetcher/internal/config"
	"github.com/crawl-policy-index/fetcher/internal/fetch"
	"github.com/crawl-policy-index/fetcher/internal/panel"
	"github.com/crawl-policy-index/fetcher/internal/store"
)

func main() {
	cfgPath := flag.String("config", "../config/dev.yml", "config YAML")
	panelPath := flag.String("panel", "", "panel CSV (overrides config)")
	once := flag.Bool("once", false, "run a single pass and exit")
	runDate := flag.String("run-date", "", "YYYY-MM-DD (default UTC today)")
	shard := flag.Int("shard", -1, "run only this shard (default all)")
	flag.Parse()

	cfg, err := config.Load(*cfgPath)
	if err != nil {
		log.Fatal(err)
	}
	if *panelPath != "" {
		cfg.Panel.Path = *panelPath
	}
	date := *runDate
	if date == "" {
		date = store.RunDateUTC()
	}

	domains, err := panel.LoadCSV(cfg.Panel.Path)
	if err != nil {
		log.Fatal(err)
	}

	st := store.NewFS(cfg.Storage.Root)
	defer st.Close()

	done, err := st.LoadCompleted(date)
	if err != nil {
		log.Fatal(err)
	}
	htmlHomeDone, err := st.LoadResourceDomains("html_home")
	if err != nil {
		log.Fatal(err)
	}
	robotsSHA, err := st.LoadTodayContentSHA(date, "robots_txt")
	if err != nil {
		log.Fatal(err)
	}
	uaToken := fetch.UAProductToken(cfg.Fetcher.UserAgent)

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	if !*once {
		log.Printf("waiting for window; use --once to run immediately")
		<-ctx.Done()
		return
	}

	f := fetch.New(cfg, st)
	started := time.Now().UTC()
	var attempted atomic.Int64
	var blobs atomic.Int64
	var mu sync.Mutex
	byOutcome := map[string]int{}

	workers := cfg.Fetcher.WorkersPerShard
	if workers < 1 {
		workers = 8
	}
	jobs := make(chan panel.Domain)
	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for d := range jobs {
				sh := panel.Shard(d.Domain, cfg.Fetcher.Shards)
				if *shard >= 0 && sh != *shard {
					continue
				}
				sitemapURL := ""
				robotsBody := []byte(nil)
				for _, resource := range cfg.Fetcher.Resources {
					key := d.Domain + "|" + resource
					mu.Lock()
					_, already := done[key]
					_, htmlDone := htmlHomeDone[d.Domain]
					sha := robotsSHA[d.Domain]
					mu.Unlock()
					if already {
						continue
					}
					if resource == "html_home" {
						if htmlDone {
							continue
						}
						body := robotsBody
						if body == nil && sha != "" {
							if got, rerr := st.GetBlob(sha); rerr == nil {
								body = got
							}
						}
						if body != nil && !fetch.AllowsHomepage(body, uaToken) {
							obs := fetch.SkippedRobotsObservation(d.Domain, resource, date, cfg.Panel.Version, cfg.Fetcher.FetcherVersion)
							if err := st.WriteObservation(sh, obs); err != nil {
								log.Printf("write obs: %v", err)
								continue
							}
							mu.Lock()
							done[key] = struct{}{}
							htmlHomeDone[d.Domain] = struct{}{}
							byOutcome[obs.Outcome]++
							mu.Unlock()
							attempted.Add(1)
							continue
						}
					}
					var obs store.Observation
					var err error
					if resource == "sitemap_xml" && sitemapURL != "" {
						obs, err = f.FetchAt(ctx, d.Domain, resource, date, cfg.Panel.Version, sitemapURL)
					} else {
						obs, err = f.Fetch(ctx, d.Domain, resource, date, cfg.Panel.Version)
					}
					if err != nil {
						if ctx.Err() != nil {
							return
						}
						log.Printf("fetch error %s %s: %v", d.Domain, resource, err)
						continue
					}
					if resource == "robots_txt" && obs.Outcome == fetch.OutcomeOK && obs.ContentSHA256 != "" {
						if body, rerr := st.GetBlob(obs.ContentSHA256); rerr == nil {
							sitemapURL = fetch.ChooseSitemapURL(d.Domain, fetch.DeclaredSitemaps(body))
							robotsBody = body
							mu.Lock()
							robotsSHA[d.Domain] = obs.ContentSHA256
							mu.Unlock()
						}
					}
					if resource == "html_home" {
						mu.Lock()
						htmlHomeDone[d.Domain] = struct{}{}
						mu.Unlock()
					}
					if err := st.WriteObservation(sh, obs); err != nil {
						log.Printf("write obs: %v", err)
						continue
					}
					attempted.Add(1)
					if obs.BlobWritten {
						blobs.Add(1)
					}
					mu.Lock()
					byOutcome[obs.Outcome]++
					mu.Unlock()
				}
			}
		}()
	}
	for _, d := range domains {
		select {
		case <-ctx.Done():
		case jobs <- d:
		}
	}
	close(jobs)
	wg.Wait()

	mu.Lock()
	outcomes := byOutcome
	mu.Unlock()
	unexplained := 0
	for _, k := range []string{"timeout", "dns_error", "tls_error", "conn_refused", "rate_limited"} {
		unexplained += outcomes[k]
	}
	att := int(attempted.Load())
	rate := 0.0
	if att > 0 {
		rate = float64(unexplained) / float64(att)
	}
	m := store.Manifest{
		RunDate:                date,
		PanelVersion:           cfg.Panel.Version,
		FetcherVersion:         cfg.Fetcher.FetcherVersion,
		StartedAt:              started.Format(time.RFC3339Nano),
		FinishedAt:             time.Now().UTC().Format(time.RFC3339Nano),
		DomainsInPanel:         len(domains),
		Attempted:              att,
		ByOutcome:              outcomes,
		BlobsWritten:           int(blobs.Load()),
		UnexplainedFailureRate: rate,
		Complete:               ctx.Err() == nil,
	}
	if err := st.WriteManifest(m); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("complete=%v attempted=%d blobs=%d unexplained=%.4f\n", m.Complete, m.Attempted, m.BlobsWritten, m.UnexplainedFailureRate)
}
