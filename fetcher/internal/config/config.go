package config

import (
	"os"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Panel    PanelConfig    `yaml:"panel"`
	Storage  StorageConfig  `yaml:"storage"`
	Fetcher  FetcherConfig  `yaml:"fetcher"`
	Database DatabaseConfig `yaml:"database"`
}

type PanelConfig struct {
	Version string `yaml:"version"`
	Path    string `yaml:"path"`
}

type StorageConfig struct {
	Backend string `yaml:"backend"`
	Root    string `yaml:"root"`
}

type DatabaseConfig struct {
	DSN string `yaml:"dsn"`
}

type FetcherConfig struct {
	Resources         []string          `yaml:"resources"`
	Shards            int               `yaml:"shards"`
	WorkersPerShard   int               `yaml:"workers_per_shard"`
	GlobalRateLimit   float64           `yaml:"global_rate_limit_rps"`
	PerHostInflight   int               `yaml:"per_host_inflight"`
	PerIPConcurrent   int               `yaml:"per_ip_concurrent"`
	Timeouts          Timeouts          `yaml:"timeouts"`
	MaxRedirects      int               `yaml:"max_redirects"`
	SizeCapsBytes     map[string]int    `yaml:"size_caps_bytes"`
	Retry             RetryConfig       `yaml:"retry"`
	UserAgent         string            `yaml:"user_agent"`
	FetcherVersion    string            `yaml:"fetcher_version"`
	ForceBaseURL      string            `yaml:"force_base_url"`
	RetryBackoffZero  bool              `yaml:"retry_backoff_zero"`
}

type Timeouts struct {
	ConnectS int `yaml:"connect_s"`
	TLSS     int `yaml:"tls_s"`
	TotalS   int `yaml:"total_s"`
}

type RetryConfig struct {
	Attempts int     `yaml:"attempts"`
	BackoffS []float64 `yaml:"backoff_s"`
}

func Load(path string) (Config, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return Config{}, err
	}
	var cfg Config
	if err := yaml.Unmarshal(b, &cfg); err != nil {
		return Config{}, err
	}
	if cfg.Fetcher.Shards < 1 {
		cfg.Fetcher.Shards = 1
	}
	if cfg.Fetcher.PerHostInflight < 1 {
		cfg.Fetcher.PerHostInflight = 1
	}
	if cfg.Fetcher.PerIPConcurrent < 1 {
		cfg.Fetcher.PerIPConcurrent = 4
	}
	if cfg.Fetcher.MaxRedirects == 0 {
		cfg.Fetcher.MaxRedirects = 3
	}
	if cfg.Fetcher.UserAgent == "" {
		cfg.Fetcher.UserAgent = "CrawlPolicyIndex/1.0 (+https://crawlpolicyindex.org/bot)"
	}
	if cfg.Fetcher.FetcherVersion == "" {
		cfg.Fetcher.FetcherVersion = "0.1.0"
	}
	if len(cfg.Fetcher.Resources) == 0 {
		cfg.Fetcher.Resources = []string{"robots_txt", "llms_txt", "sitemap_xml"}
	}
	if cfg.Fetcher.SizeCapsBytes == nil {
		cfg.Fetcher.SizeCapsBytes = map[string]int{
			"robots_txt":  1 << 20,
			"llms_txt":    2 << 20,
			"sitemap_xml": 10 << 20,
			"html_home":   512 << 10,
		}
	} else if _, ok := cfg.Fetcher.SizeCapsBytes["html_home"]; !ok {
		cfg.Fetcher.SizeCapsBytes["html_home"] = 512 << 10
	}
	if cfg.Storage.Root == "" {
		cfg.Storage.Root = "data/store"
	}
	return cfg, nil
}
