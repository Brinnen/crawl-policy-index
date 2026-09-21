package fetch

import "testing"

func TestAllowsHomepage(t *testing.T) {
	cases := []struct {
		name string
		body string
		ua   string
		want bool
	}{
		{"empty", "", "CrawlPolicyIndex", true},
		{"star admin only", "User-agent: *\nDisallow: /admin\n", "CrawlPolicyIndex", true},
		{"star blocks all", "User-agent: *\nDisallow: /\n", "CrawlPolicyIndex", false},
		{"named blocks us", "User-agent: CrawlPolicyIndex\nDisallow: /\nUser-agent: *\nAllow: /\n", "CrawlPolicyIndex", false},
		{"allow wins equal", "User-agent: *\nDisallow: /\nAllow: /\n", "CrawlPolicyIndex", true},
		{"gptbot only", "User-agent: GPTBot\nDisallow: /\n", "CrawlPolicyIndex", true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := AllowsHomepage([]byte(tc.body), tc.ua)
			if got != tc.want {
				t.Fatalf("got %v want %v", got, tc.want)
			}
		})
	}
}
