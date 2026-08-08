"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { StepSection } from "@/components/friendly/StepSection";
import { ClientPicker } from "@/components/friendly/ClientPicker";
import { GuidedSubmitButton } from "@/components/friendly/GuidedSubmitButton";
import { ResultBanner } from "@/components/friendly/ResultBanner";
import { api } from "@/lib/api";

export default function QuickLogPage() {
  const { data: clients, isError: clientsError } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.clients.list(),
    retry: 1,
  });
  const [selectedClient, setSelectedClient] = useState("");
  const [note, setNote] = useState("");
  const [situation, setSituation] = useState("");
  const [result, setResult] = useState<{ ok: boolean; message?: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const missing: string[] = [];
  if (!selectedClient) missing.push("① 利用者を選ぶ");
  if (!note.trim()) missing.push("② 内容を書く");

  const handleSubmit = async () => {
    if (!selectedClient || !note.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = (await api.quicklog.create({
        client_name: selectedClient,
        note,
        situation: situation || undefined,
      })) as { status: string; message?: string };
      if (res.status === "success") {
        setResult({ ok: true });
        setNote("");
        setSituation("");
      } else {
        setResult({ ok: false, message: res.message });
      }
    } catch {
      setResult({ ok: false });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">クイックログ</h2>
      <p className="text-base text-muted-foreground">
        今日の様子や気になったことを、短い文章で記録できます。
      </p>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">簡易記録</CardTitle>
          <p className="text-sm text-muted-foreground">
            上から順番に①→②と進めてください。
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <StepSection
            step={1}
            title="利用者を選ぶ"
            state={selectedClient ? "done" : "active"}
          >
            <ClientPicker
              clients={clients || []}
              value={selectedClient}
              onChange={setSelectedClient}
              loadError={clientsError}
            />
          </StepSection>

          <StepSection
            step={2}
            title="内容を書く"
            state={note.trim() ? "done" : selectedClient ? "active" : "waiting"}
          >
            <div className="space-y-3">
              <Textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={4}
                placeholder="例: 昼食のあと、少し不安そうな様子。声かけで落ち着いた。"
                className="text-base"
              />
              <div>
                <label className="text-sm font-medium mb-1 block">
                  場面（任意・あとで書けます）
                </label>
                <input
                  value={situation}
                  onChange={(e) => setSituation(e.target.value)}
                  className="w-full h-12 border-2 rounded-lg px-3 text-base bg-background"
                  placeholder="例: 食事、通所、レクリエーション"
                />
              </div>
            </div>
          </StepSection>

          <GuidedSubmitButton
            missing={missing}
            loading={loading}
            loadingText="記録しています…"
            onClick={handleSubmit}
          >
            記録する
          </GuidedSubmitButton>

          {result && (
            <ResultBanner
              kind={result.ok ? "success" : "error"}
              message={result.ok ? "記録しました。" : "記録できませんでした。"}
              action={
                result.ok
                  ? undefined
                  : result.message ||
                    "インターネット接続を確認して、もう一度「記録する」を押してください。"
              }
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
