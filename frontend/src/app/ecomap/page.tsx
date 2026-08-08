"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { EcomapViewer } from "@/components/domain/EcomapViewer";
import { api } from "@/lib/api";

const CATEGORY_LABELS: Record<string, string> = {
  client: "クライアント",
  ngActions: "禁忌事項",
  carePreferences: "ケア指示",
  keyPersons: "キーパーソン",
  guardians: "後見人",
  hospitals: "医療機関",
  certificates: "手帳・受給者証",
  conditions: "障害・状態",
  supporters: "支援者",
  services: "サービス事業所",
};

export default function EcomapPage() {
  const [selectedClient, setSelectedClient] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState("full_view");

  const { data: clients, isError: clientsError } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.clients.list(),
    retry: 1,
  });

  const { data: templates } = useQuery({
    queryKey: ["ecomap-templates"],
    queryFn: () => api.ecomap.templates(),
    retry: 1,
  });

  const { data: colors } = useQuery({
    queryKey: ["ecomap-colors"],
    queryFn: () => api.ecomap.colors(),
    retry: 1,
  });

  const {
    data: ecomapData,
    isLoading,
    isError: ecomapError,
  } = useQuery({
    queryKey: ["ecomap", selectedClient, selectedTemplate],
    queryFn: () => api.ecomap.get(selectedClient, selectedTemplate),
    enabled: !!selectedClient,
    retry: 1,
  });

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">エコマップ</h2>

      {/* Controls */}
      <div className="flex gap-4 items-end flex-wrap">
        <div>
          <label className="text-sm font-medium mb-1 block">
            クライアント
          </label>
          <select
            value={selectedClient}
            onChange={(e) => setSelectedClient(e.target.value)}
            className="border rounded px-3 py-2 text-sm min-w-[200px]"
          >
            <option value="">選択してください</option>
            {clients?.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex gap-2">
          {templates?.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedTemplate(t.id)}
              className={`px-3 py-2 rounded text-sm ${
                selectedTemplate === t.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80"
              }`}
              title={t.description}
            >
              {t.name}
            </button>
          ))}
        </div>
      </div>

      {/* Graph */}
      {clientsError ? (
        <Card>
          <CardContent className="pt-6 text-center text-destructive">
            クライアント一覧の取得に失敗しました
          </CardContent>
        </Card>
      ) : !selectedClient ? (
        <Card>
          <CardContent className="pt-6 text-center text-muted-foreground">
            クライアントを選択するとエコマップが表示されます
          </CardContent>
        </Card>
      ) : isLoading ? (
        <Card>
          <CardContent className="pt-6 text-center text-muted-foreground">
            読み込み中...
          </CardContent>
        </Card>
      ) : ecomapError ? (
        <Card>
          <CardContent className="pt-6 text-center text-destructive">
            エコマップの取得に失敗しました
          </CardContent>
        </Card>
      ) : ecomapData ? (
        <EcomapViewer key={`${selectedClient}-${selectedTemplate}`} data={ecomapData} />
      ) : null}

      {/* Legend */}
      {colors && (
        <div className="flex gap-3 flex-wrap">
          {Object.entries(colors).map(([cat, color]) => (
            <div key={cat} className="flex items-center gap-1.5">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: color as string }}
              />
              <span className="text-xs text-muted-foreground">
                {CATEGORY_LABELS[cat] || cat}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
