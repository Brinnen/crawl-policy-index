export const PURPOSE_LABELS: Record<string, string> = {
  training: "Training AI",
  search_index: "AI search",
  user_fetch: "When a person asks",
  opt_out_token: "Opt-out signal",
  agentic: "Autonomous agent",
  unknown: "Unclear",
  blanket: "Block all bots",
};

export const VERTICAL_LABELS: Record<string, string> = {
  news: "News",
  social: "Social",
  ecommerce: "Shop",
  search: "Search",
  streaming: "Video",
  tech: "Technology",
  travel: "Travel",
  jobs: "Jobs",
  directory: "Directory",
  weather: "Weather",
  gov: "Government",
  edu: "Education",
  other: "Unknown",
};

export const LANGUAGE_LABELS: Record<string, string> = {
  en: "English",
  sv: "Swedish",
  no: "Norwegian",
  nb: "Norwegian",
  nn: "Norwegian",
  da: "Danish",
  fi: "Finnish",
  is: "Icelandic",
  de: "German",
  fr: "French",
  es: "Spanish",
  it: "Italian",
  nl: "Dutch",
  pt: "Portuguese",
  pl: "Polish",
  ru: "Russian",
  ja: "Japanese",
  zh: "Chinese",
  ko: "Korean",
  ar: "Arabic",
  tr: "Turkish",
  cs: "Czech",
  hu: "Hungarian",
  ro: "Romanian",
  el: "Greek",
  he: "Hebrew",
  hi: "Hindi",
  th: "Thai",
  vi: "Vietnamese",
  id: "Indonesian",
  uk: "Ukrainian",
};

export const COUNTRY_LABELS: Record<string, string> = {
  SE: "Sweden",
  NO: "Norway",
  DK: "Denmark",
  FI: "Finland",
  IS: "Iceland",
  GB: "United Kingdom",
  IE: "Ireland",
  US: "United States",
  DE: "Germany",
  FR: "France",
  ES: "Spain",
  IT: "Italy",
  NL: "Netherlands",
  AU: "Australia",
  CA: "Canada",
  JP: "Japan",
  SG: "Singapore",
  IL: "Israel",
  QA: "Qatar",
  CN: "China",
  KR: "South Korea",
  RU: "Russia",
  BR: "Brazil",
  PL: "Poland",
};

export const STATE_LABELS: Record<string, string> = {
  BLOCKED: "Blocked",
  ALLOWED: "Allowed",
  PARTIAL: "Mixed",
};

export const BLANKET_SLUG = "wildcard-star";
export const BLANKET_TOKEN = "All bots (*)";

export function purposeLabel(value: string | undefined | null): string {
  if (!value) return "—";
  return PURPOSE_LABELS[value] ?? value.replaceAll("_", " ");
}
