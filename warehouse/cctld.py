"""Country from the domain name. Used as a product filter, not a legal domicile."""

from __future__ import annotations

MULTI = {
    "co.uk": "GB",
    "org.uk": "GB",
    "ac.uk": "GB",
    "gov.uk": "GB",
    "com.au": "AU",
    "net.au": "AU",
    "org.au": "AU",
    "co.nz": "NZ",
    "co.jp": "JP",
    "ne.jp": "JP",
    "or.jp": "JP",
    "ac.jp": "JP",
    "co.kr": "KR",
    "co.in": "IN",
    "com.br": "BR",
    "com.mx": "MX",
    "com.ar": "AR",
    "co.za": "ZA",
    "com.tr": "TR",
    "com.sg": "SG",
    "com.tw": "TW",
    "com.hk": "HK",
    "com.cn": "CN",
    "co.id": "ID",
    "com.my": "MY",
    "co.th": "TH",
    "com.ph": "PH",
    "com.vn": "VN",
    "com.ua": "UA",
    "com.pl": "PL",
    "co.il": "IL",
    "com.eg": "EG",
    "co.ke": "KE",
    "com.ng": "NG",
    "com.pk": "PK",
    "com.sa": "SA",
    "com.ae": "AE",
    "com.bd": "BD",
}

# Generic / infra suffixes — not a country filter.
GENERIC = {
    "com", "net", "org", "edu", "gov", "mil", "int", "info", "biz", "name",
    "pro", "xxx", "aero", "asia", "cat", "coop", "jobs", "mobi", "museum",
    "tel", "travel", "app", "dev", "page", "site", "online", "store", "shop",
    "blog", "news", "cloud", "xyz", "top", "icu", "club", "live", "life",
    "world", "today", "tech", "io", "ai", "tv", "cc", "ws", "me", "co",
    "us",  # often used as vanity, still map us → US below via ISO; keep
}

ISO2 = {
    "ac", "ad", "ae", "af", "ag", "al", "am", "ao", "ar", "at", "au", "az",
    "ba", "bb", "bd", "be", "bf", "bg", "bh", "bi", "bj", "bn", "bo", "br",
    "bs", "bt", "bw", "by", "bz", "ca", "cd", "cf", "cg", "ch", "ci", "cl",
    "cm", "cn", "co", "cr", "cu", "cv", "cy", "cz", "de", "dj", "dk", "dm",
    "do", "dz", "ec", "ee", "eg", "er", "es", "et", "fi", "fj", "fm", "fr",
    "ga", "gb", "ge", "gh", "gm", "gn", "gq", "gr", "gt", "gw", "gy", "hk",
    "hn", "hr", "ht", "hu", "id", "ie", "il", "in", "iq", "ir", "is", "it",
    "jm", "jo", "jp", "ke", "kg", "kh", "ki", "km", "kn", "kp", "kr", "kw",
    "kz", "la", "lb", "lc", "li", "lk", "lr", "ls", "lt", "lu", "lv", "ly",
    "ma", "mc", "md", "me", "mg", "mk", "ml", "mm", "mn", "mo", "mr", "mt",
    "mu", "mv", "mw", "mx", "my", "mz", "na", "ne", "ng", "ni", "nl", "no",
    "np", "nr", "nz", "om", "pa", "pe", "pg", "ph", "pk", "pl", "ps", "pt",
    "py", "qa", "ro", "rs", "ru", "rw", "sa", "sb", "sc", "sd", "se", "sg",
    "si", "sk", "sl", "sm", "sn", "so", "sr", "ss", "st", "sv", "sy", "sz",
    "td", "tg", "th", "tj", "tl", "tm", "tn", "to", "tr", "tt", "tv", "tw",
    "tz", "ua", "ug", "uk", "uy", "uz", "va", "vc", "ve", "vn", "vu", "ws",
    "ye", "za", "zm", "zw",
}

# Vanity / generic 2-letter and 3-letter we do not treat as a country.
NOT_COUNTRY = {
    "com", "net", "org", "edu", "gov", "mil", "int", "io", "ai", "tv", "cc",
    "ws", "me", "co", "gg", "to", "fm", "am", "tk", "ml", "cf", "ga", "gq",
}


def country_from_domain(domain: str) -> str:
    host = (domain or "").strip().lower().rstrip(".")
    if not host or "." not in host:
        return ""
    for suffix, cc in MULTI.items():
        if host == suffix or host.endswith("." + suffix):
            return cc
    tld = host.rsplit(".", 1)[-1]
    if tld in NOT_COUNTRY:
        return ""
    if tld == "uk":
        return "GB"
    if tld == "us":
        return "US"
    if len(tld) == 2 and tld in ISO2:
        return tld.upper()
    return ""


def category_from_domain(domain: str, labeled: str = "") -> str:
    if labeled and labeled != "other":
        return labeled
    host = (domain or "").strip().lower()
    if host.endswith(".edu") or ".ac." in host or host.endswith(".ac.uk"):
        return "edu"
    if host.endswith(".gov") or ".gov." in host:
        return "gov"
    return "other"
