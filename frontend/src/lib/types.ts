export interface ClientSummary {
  name: string;
  dob: string | null;
  age: number | null;
  blood_type: string | null;
  conditions: string[];
}

export interface NgAction {
  action: string;
  reason: string | null;
  risk_level: string;
}

export interface DashboardStats {
  client_count: number;
  log_count_this_month: number;
  renewal_alerts: number;
}

export interface RenewalAlert {
  client_name: string;
  certificate_type: string;
  next_renewal_date: string;
  days_remaining: number;
}

export interface ActivityEntry {
  date: string;
  client_name: string;
  action: string;
  summary: string;
}

export interface SystemStatus {
  neo4j_available: boolean;
}

export interface EcomapNode {
  id: string;
  label: string;
  node_label: string;
  category: string;
  color: string;
  properties: Record<string, unknown>;
}

export interface EcomapEdge {
  source: string;
  target: string;
  label: string;
}

export interface EcomapData {
  client_name: string;
  template: string;
  nodes: EcomapNode[];
  edges: EcomapEdge[];
}

export interface EcomapTemplate {
  id: string;
  name: string;
  description: string;
}

export interface ClientCreate {
  name: string;
  dob?: string;
  blood_type?: string;
  conditions?: string[];
}

export interface ClientUpdate {
  dob?: string;
  blood_type?: string;
}

export interface ClientDeleteResult {
  status: string;
  client_name: string;
  deleted_count: number;
}

export interface ClientDetail {
  name: string;
  dob: string | null;
  age: number | null;
  blood_type: string | null;
  conditions: { name: string; diagnosedDate?: string }[];
  ng_actions: NgAction[];
  care_preferences: { category: string; instruction: string; priority?: string }[];
  key_persons: { name: string; relationship?: string; phone?: string; rank?: number }[];
  certificates: Record<string, unknown>[];
  hospital: Record<string, unknown> | null;
  guardian: Record<string, unknown> | null;
}

export interface MeetingRecord {
  date: string | null;
  title: string | null;
  transcript: string | null;
  note: string | null;
  client_name: string | null;
}
