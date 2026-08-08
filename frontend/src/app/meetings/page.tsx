"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AudioUploader } from "@/components/domain/AudioUploader";
import { api } from "@/lib/api";

export default function MeetingsPage() {
  const [selectedClient, setSelectedClient] = useState("");
  const { data: clients, isError: clientsError } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.clients.list(),
    retry: 1,
  });
  const { data: meetings, isError: meetingsError, refetch } = useQuery({
    queryKey: ["meetings", selectedClient],
    queryFn: () => api.meetings.list(selectedClient),
    enabled: !!selectedClient,
    retry: 1,
  });

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">面談記録</h2>
      <AudioUploader clients={clients || []} onUploaded={refetch} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">面談記録一覧</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <select
            value={selectedClient}
            onChange={(e) => setSelectedClient(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
          >
            <option value="">クライアントを選択</option>
            {clients?.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
          {clientsError ? (
            <p className="text-sm text-destructive">クライアント一覧の取得に失敗しました</p>
          ) : meetingsError ? (
            <p className="text-sm text-destructive">面談記録の取得に失敗しました</p>
          ) : !meetings?.length ? (
            <p className="text-sm text-muted-foreground">
              {selectedClient ? "記録なし" : "クライアントを選択してください"}
            </p>
          ) : (
            <div className="space-y-3">
              {meetings.map((m, i) => (
                <div key={i} className="border rounded p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium">{m.title || "無題"}</span>
                    <span className="text-xs text-muted-foreground">{m.date}</span>
                  </div>
                  {m.note && (
                    <p className="text-sm text-muted-foreground mb-2">{m.note}</p>
                  )}
                  {m.transcript && (
                    <details className="text-sm">
                      <summary className="cursor-pointer text-primary">
                        文字起こしを表示
                      </summary>
                      <p className="mt-2 p-2 bg-muted rounded whitespace-pre-wrap">
                        {m.transcript}
                      </p>
                    </details>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
