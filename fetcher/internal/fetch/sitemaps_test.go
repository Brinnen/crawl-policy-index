package fetch

import "testing"

func TestDeclaredSitemaps(t *testing.T) {
	body := []byte("User-agent: *\nDisallow: /\nSitemap: https://www.example.com/sitemap_index.xml\nSitemap: https://www.example.com/news.xml\n")
	got := DeclaredSitemaps(body)
	if len(got) != 2 || got[0] != "https://www.example.com/sitemap_index.xml" {
		t.Fatalf("got %#v", got)
	}
}

func TestChooseSitemapPrefersDeclaredSameSite(t *testing.T) {
	u := ChooseSitemapURL("example.com", []string{"https://www.example.com/sitemap_index.xml"})
	if u != "https://www.example.com/sitemap_index.xml" {
		t.Fatalf("got %s", u)
	}
}

func TestChooseSitemapRelativePath(t *testing.T) {
	u := ChooseSitemapURL("example.com", []string{"/sitemaps/site.xml"})
	if u != "https://example.com/sitemaps/site.xml" {
		t.Fatalf("got %s", u)
	}
}

func TestChooseSitemapFallsBack(t *testing.T) {
	u := ChooseSitemapURL("example.com", nil)
	if u != "https://example.com/sitemap.xml" {
		t.Fatalf("got %s", u)
	}
}
