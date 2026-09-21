package fetch

import (
	"strings"

	"github.com/crawl-policy-index/fetcher/internal/store"
)

const OutcomeSkippedRobots = "skipped_robots"

// AllowsHomepage reports whether robots.txt lets uaToken fetch "/".
// Empty or unreadable files default to allow (no rules means allow).
// Exact User-agent token match, then the * group. This is not a country signal.
func AllowsHomepage(body []byte, uaToken string) bool {
	if len(body) == 0 {
		return true
	}
	groups := parseUAGroups(string(body))
	if len(groups) == 0 {
		return true
	}
	needle := strings.ToLower(strings.TrimSpace(uaToken))
	var matched []uaGroup
	for _, g := range groups {
		for _, agent := range g.agents {
			if strings.ToLower(agent) == needle {
				matched = append(matched, g)
				break
			}
		}
	}
	if len(matched) == 0 {
		for _, g := range groups {
			for _, agent := range g.agents {
				if agent == "*" {
					matched = append(matched, g)
					break
				}
			}
		}
	}
	if len(matched) == 0 {
		return true
	}
	var rules []rule
	for _, g := range matched {
		rules = append(rules, g.rules...)
	}
	return pathAllowed(rules, "/")
}

type rule struct {
	allow  bool
	value  string
	length int
}

type uaGroup struct {
	agents []string
	rules  []rule
}

func parseUAGroups(text string) []uaGroup {
	var groups []uaGroup
	var current *uaGroup
	sawNonUA := false
	text = strings.ReplaceAll(strings.ReplaceAll(text, "\r\n", "\n"), "\r", "\n")
	for _, raw := range strings.Split(text, "\n") {
		line := raw
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if line == "" || !strings.Contains(line, ":") {
			continue
		}
		name, value, _ := strings.Cut(line, ":")
		name = strings.ToLower(strings.TrimSpace(name))
		value = strings.TrimSpace(value)
		if name == "user-agent" {
			if current == nil || sawNonUA {
				groups = append(groups, uaGroup{})
				current = &groups[len(groups)-1]
				sawNonUA = false
			}
			if value != "" {
				current.agents = append(current.agents, value)
			}
			continue
		}
		if current == nil {
			continue
		}
		if name == "sitemap" {
			continue
		}
		sawNonUA = true
		if name != "allow" && name != "disallow" {
			continue
		}
		if value == "" {
			continue
		}
		current.rules = append(current.rules, rule{
			allow:  name == "allow",
			value:  value,
			length: len(value),
		})
	}
	return groups
}

func pathAllowed(rules []rule, path string) bool {
	bestAllow := -1
	bestDisallow := -1
	for _, r := range rules {
		if !pathMatches(r.value, path) {
			continue
		}
		if r.allow {
			if r.length > bestAllow {
				bestAllow = r.length
			}
			continue
		}
		if r.length > bestDisallow {
			bestDisallow = r.length
		}
	}
	if bestDisallow < 0 {
		return true
	}
	if bestAllow < 0 {
		return false
	}
	if bestAllow != bestDisallow {
		return bestAllow > bestDisallow
	}
	return true
}

func UAProductToken(userAgent string) string {
	ua := strings.TrimSpace(userAgent)
	if ua == "" {
		return "CrawlPolicyIndex"
	}
	token := ua
	if i := strings.IndexAny(token, "/ \t"); i >= 0 {
		token = token[:i]
	}
	if token == "" {
		return "CrawlPolicyIndex"
	}
	return token
}

func SkippedRobotsObservation(domain, resource, runDate, panelVersion, fetcherVersion string) store.Observation {
	msg := "homepage skipped; robots.txt disallows / for this user-agent"
	return store.Observation{
		PanelVersion:   panelVersion,
		RunDate:        runDate,
		Domain:         domain,
		Resource:       resource,
		FetchedAt:      store.NowUTC(),
		URLRequested:   "https://" + domain + "/",
		Outcome:        OutcomeSkippedRobots,
		FetcherVersion: fetcherVersion,
		ErrorDetail:    &msg,
	}
}

func pathMatches(pattern, path string) bool {
	anchored := strings.HasSuffix(pattern, "$")
	pat := strings.TrimSuffix(pattern, "$")
	if strings.Contains(pat, "*") {
		head, tail, _ := strings.Cut(pat, "*")
		if !strings.HasPrefix(path, head) {
			return false
		}
		rest := path[len(head):]
		if tail == "" {
			return !anchored || rest == ""
		}
		if anchored {
			return strings.HasSuffix(path, tail) && strings.HasPrefix(path, head)
		}
		return strings.Contains(rest, tail)
	}
	if anchored {
		return path == pat
	}
	return strings.HasPrefix(path, pat)
}
