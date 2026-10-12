"""Country only when the homepage states an address. Never from html lang."""

from __future__ import annotations

import re

# Explicit address / contact fields. Not og:locale, not html lang.
_ADDRESS_COUNTRY = re.compile(
    r"""["']addressCountry["']\s*:\s*["']([^"']+)["']""",
    re.I,
)
_META_COUNTRY = re.compile(
    r"""<meta\b[^>]*(?:property|name)\s*=\s*['"](?:business:contact_data:country_name|og:country-name)['"][^>]*content\s*=\s*['"]([^'"]+)['"]""",
    re.I,
)
_META_COUNTRY_SWAP = re.compile(
    r"""<meta\b[^>]*content\s*=\s*['"]([^'"]+)['"][^>]*(?:property|name)\s*=\s*['"](?:business:contact_data:country_name|og:country-name)['"]""",
    re.I,
)

# Names the site itself writes next to an address. Not a geo guess.
_NAMES = {
    "UNITED STATES": "US",
    "USA": "US",
    "U.S.": "US",
    "U.S.A.": "US",
    "UNITED KINGDOM": "GB",
    "UK": "GB",
    "GREAT BRITAIN": "GB",
    "SWEDEN": "SE",
    "GERMANY": "DE",
    "FRANCE": "FR",
    "SPAIN": "ES",
    "ITALY": "IT",
    "NETHERLANDS": "NL",
    "JAPAN": "JP",
    "CHINA": "CN",
    "INDIA": "IN",
    "BRAZIL": "BR",
    "CANADA": "CA",
    "AUSTRALIA": "AU",
}

_ISO2 = {
    "AD", "AE", "AF", "AG", "AL", "AM", "AO", "AR", "AT", "AU", "AZ",
    "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BN", "BO", "BR",
    "BS", "BT", "BW", "BY", "BZ", "CA", "CD", "CF", "CG", "CH", "CI", "CL",
    "CM", "CN", "CO", "CR", "CU", "CV", "CY", "CZ", "DE", "DJ", "DK", "DM",
    "DO", "DZ", "EC", "EE", "EG", "ER", "ES", "ET", "FI", "FJ", "FR",
    "GA", "GB", "GE", "GH", "GM", "GN", "GQ", "GR", "GT", "GW", "GY", "HK",
    "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IN", "IQ", "IR", "IS", "IT",
    "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN", "KP", "KR", "KW",
    "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY",
    "MA", "MC", "MD", "ME", "MG", "MK", "ML", "MM", "MN", "MO", "MR", "MT",
    "MU", "MV", "MW", "MX", "MY", "MZ", "NA", "NE", "NG", "NI", "NL", "NO",
    "NP", "NR", "NZ", "OM", "PA", "PE", "PG", "PH", "PK", "PL", "PS", "PT",
    "PY", "QA", "RO", "RS", "RU", "RW", "SA", "SB", "SC", "SD", "SE", "SG",
    "SI", "SK", "SL", "SM", "SN", "SO", "SR", "SS", "ST", "SV", "SY", "SZ",
    "TD", "TG", "TH", "TJ", "TL", "TM", "TN", "TR", "TT", "TW",
    "TZ", "UA", "UG", "US", "UY", "UZ", "VA", "VC", "VE", "VN", "YE",
    "ZA", "ZM", "ZW",
}


def _norm(value: str) -> str:
    token = (value or "").strip()
    if not token:
        return ""
    if len(token) == 2 and token.isalpha():
        code = token.upper()
        return code if code in _ISO2 else ""
    return _NAMES.get(token.upper(), "")


def country_from_html(body: bytes | str) -> str:
    if isinstance(body, bytes):
        text = body[:80_000].decode("utf-8", errors="replace")
    else:
        text = body[:80_000]
    for rx in (_ADDRESS_COUNTRY, _META_COUNTRY, _META_COUNTRY_SWAP):
        m = rx.search(text)
        if m and (code := _norm(m.group(1))):
            return code
    return ""
