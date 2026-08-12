const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  dashboard: {
    stats: () => fetchApi<import("./types").DashboardStats>("/api/dashboard/stats"),
    alerts: () => fetchApi<import("./types").RenewalAlert[]>("/api/dashboard/alerts"),
    activity: () => fetchApi<import("./types").ActivityEntry[]>("/api/dashboard/activity"),
  },
  clients: {
    list: (kanaPrefix?: string) =>
      fetchApi<import("./types").ClientSummary[]>(
        `/api/clients${kanaPrefix ? `?kana_prefix=${kanaPrefix}` : ""}`
      ),
    get: (name: string) => fetchApi(`/api/clients/${encodeURIComponent(name)}`),
    emergency: (name: string) => fetchApi(`/api/clients/${encodeURIComponent(name)}/emergency`),
    logs: (name: string) => fetchApi(`/api/clients/${encodeURIComponent(name)}/logs`),
    create: (data: import("./types").ClientCreate) =>
      fetchApi<import("./types").ClientDetail>("/api/clients", { method: "POST", body: JSON.stringify(data) }),
    update: (name: string, data: import("./types").ClientUpdate) =>
      fetchApi<import("./types").ClientDetail>(`/api/clients/${encodeURIComponent(name)}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (name: string) =>
      fetchApi<import("./types").ClientDeleteResult>(`/api/clients/${encodeURIComponent(name)}`, { method: "DELETE" }),
  },
  system: {
    status: () => fetchApi<import("./types").SystemStatus>("/api/system/status"),
  },
  quicklog: {
    create: (data: {
      client_name: string;
      note: string;
      situation?: string;
      emotion?: string;
      trigger_tag?: string;
      context?: string;
      action?: string;
      effectiveness?: string;
    }) =>
      fetchApi("/api/quicklog", { method: "POST", body: JSON.stringify(data) }),
  },
  meetings: {
    upload: async (data: {
      clientName: string;
      file?: File;
      text?: string;
      title?: string;
      note?: string;
    }) => {
      const formData = new FormData();
      formData.append("client_name", data.clientName);
      if (data.file) formData.append("file", data.file);
      if (data.text) formData.append("text", data.text);
      if (data.title) formData.append("title", data.title);
      if (data.note) formData.append("note", data.note);
      const res = await fetch(`${API_BASE}/api/meetings/upload`, { method: "POST", body: formData });
      if (!res.ok) throw new Error(`Upload error: ${res.status}`);
      return res.json();
    },
    list: (clientName: string) =>
      fetchApi<import("./types").MeetingRecord[]>(`/api/meetings/${encodeURIComponent(clientName)}`),
  },
  ecomap: {
    templates: () => fetchApi<import("./types").EcomapTemplate[]>("/api/ecomap/templates"),
    colors: () => fetchApi<Record<string, string>>("/api/ecomap/colors"),
    get: (name: string, template?: string) =>
      fetchApi<import("./types").EcomapData>(
        `/api/ecomap/${encodeURIComponent(name)}?template=${template || "full_view"}`
      ),
  },
  graph: {
    explore: (params?: {
      startLabel?: string;
      startName?: string;
      maxDepth?: number;
      maxNodes?: number;
    }) => {
      const sp = new URLSearchParams();
      if (params?.startLabel) sp.set("startLabel", params.startLabel);
      if (params?.startName) sp.set("startName", params.startName);
      if (params?.maxDepth) sp.set("maxDepth", String(params.maxDepth));
      if (params?.maxNodes) sp.set("maxNodes", String(params.maxNodes));
      const qs = sp.toString();
      return fetchApi<{
        nodes: Array<{ id: string; label: string; name: string; properties: Record<string, unknown> }>;
        edges: Array<{ id: string; source: string; target: string; type: string; properties: Record<string, unknown> }>;
        truncated: boolean;
      }>(`/api/graph/explore${qs ? `?${qs}` : ""}`);
    },
    labels: () => fetchApi<{ labels: Array<{ label: string; count: number }> }>("/api/graph/labels"),
    stats: () => fetchApi<{ total_nodes: number; total_edges: number }>("/api/graph/stats"),
  },
};
