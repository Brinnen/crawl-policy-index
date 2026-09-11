export type LabSummary = {
  trusted_robots: number;
  gptbot_named_block: number;
  gptbot_named_allow: number;
  gptbot_named_partial: number;
  gptbot_named_block_grouped: number;
  gptbot_blanket_block?: number | null;
  openai_split: number;
  googlebot_named_block: number;
  calendar_observations: number;
};

export type NamedRow = {
  domain: string;
  state: "ALLOWED" | "BLOCKED" | "PARTIAL";
  group_key: string;
  valid_from: string;
};

export type GroupedRow = {
  group_key: string;
  domain_rows: number;
  named_block_rows: number;
  named_allow_rows: number;
  named_partial_rows: number;
};

export type LabExport = {
  generated_at: string;
  panel_version: string;
  parse_version: string;
  view: string;
  lab: true;
  verified_agents: false;
  summary: LabSummary;
  named: NamedRow[];
  blanket?: NamedRow[];
  grouped: GroupedRow[];
};
