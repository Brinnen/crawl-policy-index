package fetch

import (
	"net/url"
	"strings"

	"golang.org/x/net/publicsuffix"
)

// DeclaredSitemaps returns Sitemap: values from a robots.txt body.
// These are the site's own pointers; they beat guessing /sitemap.xml.
func DeclaredSitemaps(robotsBody []byte) []string {
	text := string(robotsBody)
	text = strings.ReplaceAll(text, "\r\n", "\n")
	text = strings.ReplaceAll(text, "\r", "\n")
	var out []string
	seen := map[string]struct{}{}
	for _, line := range strings.Split(text, "\n") {
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if line == "" || !strings.Contains(line, ":") {
			continue
		}
		name, value, _ := strings.Cut(line, ":")
		if strings.ToLower(strings.TrimSpace(name)) != "sitemap" {
			continue
		}
		value = strings.TrimSpace(value)
		if value == "" {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		out = append(out, value)
	}
	return out
}

// ChooseSitemapURL picks one URL to fetch. Schema allows one sitemap_xml
// observation per domain per day, so we take the first same-site declaration,
// else the first declaration, else https://{domain}/sitemap.xml.
func ChooseSitemapURL(domain string, declared []string) string {
	fallback := "https://" + domain + "/sitemap.xml"
	var firstAbs string
	for _, raw := range declared {
		abs := resolveSitemapURL(domain, raw)
		if abs == "" {
			continue
		}
		if firstAbs == "" {
			firstAbs = abs
		}
		if sameRegistrable(domain, abs) {
			return abs
		}
	}
	if firstAbs != "" {
		return firstAbs
	}
	return fallback
}

func resolveSitemapURL(domain, raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	if strings.HasPrefix(raw, "//") {
		raw = "https:" + raw
	}
	if strings.HasPrefix(raw, "/") {
		return "https://" + domain + raw
	}
	u, err := url.Parse(raw)
	if err != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") {
		return ""
	}
	return u.String()
}

func sameRegistrable(domain, rawURL string) bool {
	u, err := url.Parse(rawURL)
	if err != nil {
		return false
	}
	host := strings.ToLower(u.Hostname())
	domain = strings.ToLower(domain)
	a, err1 := publicsuffix.EffectiveTLDPlusOne(domain)
	b, err2 := publicsuffix.EffectiveTLDPlusOne(host)
	if err1 != nil || err2 != nil {
		return host == domain || strings.HasSuffix(host, "."+domain)
	}
	return a == b
}
