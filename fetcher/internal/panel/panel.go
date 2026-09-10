package panel

import (
	"encoding/csv"
	"fmt"
	"hash/fnv"
	"os"
	"strings"
)

type Domain struct {
	Domain     string
	Strata     string
	TrancoRank string
	Country    string
	Vertical   string
}

func LoadCSV(path string) ([]Domain, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	r := csv.NewReader(f)
	rows, err := r.ReadAll()
	if err != nil {
		return nil, err
	}
	if len(rows) < 2 {
		return nil, fmt.Errorf("panel %s: no domains", path)
	}
	out := make([]Domain, 0, len(rows)-1)
	for i, row := range rows[1:] {
		if len(row) < 1 || strings.TrimSpace(row[0]) == "" {
			return nil, fmt.Errorf("panel line %d: empty domain", i+2)
		}
		d := Domain{Domain: strings.TrimSpace(row[0])}
		if len(row) > 1 {
			d.Strata = row[1]
		}
		if len(row) > 2 {
			d.TrancoRank = row[2]
		}
		if len(row) > 3 {
			d.Country = row[3]
		}
		if len(row) > 4 {
			d.Vertical = row[4]
		}
		out = append(out, d)
	}
	return out, nil
}

func Shard(domain string, shardCount int) int {
	if shardCount <= 1 {
		return 0
	}
	h := fnv.New32a()
	_, _ = h.Write([]byte(domain))
	return int(h.Sum32() % uint32(shardCount))
}

func ResourcePath(resource string) string {
	switch resource {
	case "robots_txt":
		return "/robots.txt"
	case "llms_txt":
		return "/llms.txt"
	case "sitemap_xml":
		return "/sitemap.xml"
	default:
		return "/" + resource
	}
}
