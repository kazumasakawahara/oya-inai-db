"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MeetingRecordForm } from "@/components/domain/MeetingRecordForm";
import { ClientPicker } from "@/components/friendly/ClientPicker";
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
      <p className="text-base text-muted-foreground">
        面談の内容を記録として保存します。その場で文字を打っても、文書や録音のファイルを添付してもかまいません。
      </p>
      <MeetingRecordForm
        clients={clients || []}
        clientsError={clientsError}
        onUploaded={refetch}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">これまでの面談記録を見る</CardTitle>
          <p className="text-sm text-muted-foreground">
            利用者を選ぶと、その方の記録が表示されます。
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <ClientPicker
            clients={clients || []}
            value={selectedClient}
            onChange={setSelectedClient}
            loadError={clientsError}
          />
          {meetingsError ? (
            <p className="text-base text-destructive">
              面談記録を読み込めませんでした。ページを再読み込みしてもう一度お試しください。
            </p>
          ) : !selectedClient ? null : !meetings?.length ? (
            <p className="text-base text-muted-foreground">
              この方の面談記録はまだありません。
            </p>
          ) : (
            <div className="space-y-3">
              {meetings.map((m, i) => (
                <div key={i} className="border rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-base font-medium">{m.title || "無題"}</span>
                    <span className="text-sm text-muted-foreground">{m.date}</span>
                  </div>
                  {m.note && (
                    <p className="text-sm text-muted-foreground mb-2">{m.note}</p>
                  )}
                  {m.transcript && (
                    <details className="text-base">
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
