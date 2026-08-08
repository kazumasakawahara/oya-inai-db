// Node color mapping by Neo4j label
// Colors chosen for visibility and domain meaning
export const NODE_COLORS: Record<string, string> = {
  Client: "#2563eb",          // Blue - center of the graph
  NgAction: "#dc2626",        // Red - safety-critical (禁忌)
  CarePreference: "#16a34a",  // Green - recommended care
  Condition: "#ca8a04",       // Amber - medical conditions
  KeyPerson: "#7c3aed",       // Purple - emergency contacts
  Guardian: "#db2777",        // Pink - legal representatives
  Hospital: "#0891b2",        // Cyan - medical facilities
  Organization: "#0ea5e9",    // Sky - partner organizations
  ServiceProvider: "#14b8a6", // Teal - service providers
  Supporter: "#f97316",       // Orange - support staff
  Certificate: "#84cc16",     // Lime - official certificates
  SupportLog: "#94a3b8",      // Slate - daily logs
  LifeHistory: "#a78bfa",     // Violet - biographical
  Wish: "#fbbf24",            // Yellow - wishes
  MeetingRecord: "#6366f1",   // Indigo - meeting records
};

export const DEFAULT_NODE_COLOR = "#64748b";  // Slate gray

export function getNodeColor(label: string): string {
  return NODE_COLORS[label] || DEFAULT_NODE_COLOR;
}

export const LABEL_JP: Record<string, string> = {
  Client: "クライアント",
  NgAction: "禁忌事項",
  CarePreference: "ケア指示",
  Condition: "状態・診断",
  KeyPerson: "キーパーソン",
  Guardian: "後見人",
  Hospital: "医療機関",
  Organization: "関係機関",
  ServiceProvider: "サービス事業所",
  Supporter: "支援者",
  Certificate: "手帳",
  SupportLog: "支援記録",
  LifeHistory: "生育歴",
  Wish: "願い",
  MeetingRecord: "面談記録",
};
