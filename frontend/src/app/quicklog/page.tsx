"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";

export default function QuickLogPage() {
  const { data: clients, isError: clientsError } = useQuery({ queryKey: ["clients"], queryFn: () => api.clients.list(), retry: 1 });
  const [selectedClient, setSelectedClient] = useState("");
  const [note, setNote] = useState("");
  const [situation, setSituation] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!selectedClient || !note.trim()) return;
    setLoading(true);
    try {
      const res = await api.quicklog.create({ client_name: selectedClient, note, situation: situation || undefined }) as any;
      setResult(res.status === "success" ? "記録を登録しました。" : `エラー: ${res.message}`);
      setNote(""); setSituation("");
    } finally { setLoading(false); }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">クイックログ</h2>
      <Card>
        <CardHeader><CardTitle>簡易記録</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-1 block">クライアント</label>
            {clientsError ? (
              <p className="text-sm text-destructive">クライアント一覧の取得に失敗しました</p>
            ) : (
            <select value={selectedClient} onChange={(e) => setSelectedClient(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm">
              <option value="">選択してください</option>
              {clients?.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
            </select>
            )}
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">状況（任意）</label>
            <input value={situation} onChange={(e) => setSituation(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm" placeholder="食事、通所、レクリエーション..." />
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">内容</label>
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={4} placeholder="今日の様子や気になったことを記録..." />
          </div>
          <Button onClick={handleSubmit} disabled={!selectedClient || !note.trim() || loading}>
            {loading ? "登録中..." : "記録する"}
          </Button>
          {result && <p className="text-sm text-green-600">{result}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
