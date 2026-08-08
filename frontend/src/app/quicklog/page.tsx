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

// 保存値は installer シードデータ・insight 分析と共通の語彙
const EMOTIONS = [
  { value: "Joy", emoji: "😊", label: "喜んでいた・楽しそうだった" },
  { value: "Anxiety", emoji: "😟", label: "嫌がっていた・不安そうだった" },
  { value: "Fear", emoji: "😨", label: "パニックになった・強くおびえていた" },
  { value: "Anger", emoji: "😠", label: "怒っていた・イライラしていた" },
  { value: "Sadness", emoji: "😢", label: "悲しそうだった・元気がなかった" },
];

const SCENES = [
  { label: "食事のとき", situation: "食事", triggerTag: "食事" },
  { label: "入浴のとき", situation: "入浴", triggerTag: "入浴" },
  { label: "作業・活動中", situation: "作業", triggerTag: "作業中" },
  { label: "外出・散歩中", situation: "散歩", triggerTag: "外出" },
  { label: "ほかの人との交流", situation: "他者交流", triggerTag: "他者交流" },
  { label: "移動・送迎中", situation: "移動", triggerTag: "移動" },
  { label: "休憩中・自由時間", situation: "休憩", triggerTag: "休憩" },
  { label: "予定が変わったとき", situation: "予定変更", triggerTag: "予定変更" },
  { label: "その他", situation: "その他", triggerTag: "その他" },
];

const EFFECTIVENESS = [
  { value: "Effective", label: "うまくいった" },
  { value: "Neutral", label: "どちらともいえない" },
  { value: "Ineffective", label: "うまくいかなかった" },
];

export default function QuickLogPage() {
  const { data: clients, isError: clientsError } = useQuery({
    queryKey: ["clients"],
    queryFn: () => api.clients.list(),
    retry: 1,
  });
  const [selectedClient, setSelectedClient] = useState("");
  const [emotion, setEmotion] = useState("");
  const [scene, setScene] = useState("");
  const [context, setContext] = useState("");
  const [note, setNote] = useState("");
  const [action, setAction] = useState("");
  const [effectiveness, setEffectiveness] = useState("");
  const [result, setResult] = useState<{ ok: boolean; message?: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const missing: string[] = [];
  if (!selectedClient) missing.push("① 利用者を選ぶ");
  if (!emotion) missing.push("② 本人の様子を選ぶ");
  if (!scene) missing.push("③ 場面を選ぶ");
  if (!note.trim()) missing.push("④ くわしく書く");

  const handleSubmit = async () => {
    if (missing.length > 0) return;
    const selectedScene = SCENES.find((s) => s.label === scene);
    setLoading(true);
    setResult(null);
    try {
      const res = (await api.quicklog.create({
        client_name: selectedClient,
        note,
        situation: selectedScene?.situation,
        emotion,
        trigger_tag: selectedScene?.triggerTag,
        context: context.trim() || undefined,
        action: action.trim() || undefined,
        effectiveness: effectiveness || undefined,
      })) as { status: string; message?: string };
      if (res.status === "success") {
        setResult({ ok: true });
        setEmotion("");
        setScene("");
        setContext("");
        setNote("");
        setAction("");
        setEffectiveness("");
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
        本人が喜んだ・嫌がった・パニックになったなど、気になった出来事を記録します。
        「どんな場面で起きたか」も一緒に残すと、今後の支援のヒントになります。
      </p>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">出来事の記録</CardTitle>
          <p className="text-sm text-muted-foreground">
            上から順番に①→②→③→④と進めてください。
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
            title="本人の様子はどうでしたか"
            state={emotion ? "done" : selectedClient ? "active" : "waiting"}
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {EMOTIONS.map((e) => (
                <button
                  key={e.value}
                  type="button"
                  onClick={() => setEmotion(emotion === e.value ? "" : e.value)}
                  className={`flex items-center gap-3 p-3 rounded-lg border-2 text-left text-base transition-colors ${
                    emotion === e.value
                      ? "border-primary bg-primary/10 font-bold"
                      : "border-input bg-background hover:bg-muted"
                  }`}
                >
                  <span className="text-2xl">{e.emoji}</span>
                  <span>{e.label}</span>
                </button>
              ))}
            </div>
          </StepSection>

          <StepSection
            step={3}
            title="どんな場面でしたか"
            state={scene ? "done" : emotion ? "active" : "waiting"}
          >
            <div className="space-y-3">
              <select
                value={scene}
                onChange={(e) => setScene(e.target.value)}
                className="w-full h-12 border-2 rounded-lg px-3 text-lg bg-background"
                aria-label="場面を選ぶ"
              >
                <option value="">▼ 押して場面を選ぶ</option>
                {SCENES.map((s) => (
                  <option key={s.label} value={s.label}>
                    {s.label}
                  </option>
                ))}
              </select>
              <div>
                <label className="text-sm font-medium mb-1 block">
                  そのときの環境・きっかけ（任意）
                </label>
                <input
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  className="w-full h-12 border-2 rounded-lg px-3 text-base bg-background"
                  placeholder="例: 大きな音がした、人が多くて騒がしかった"
                />
              </div>
            </div>
          </StepSection>

          <StepSection
            step={4}
            title="くわしく書く"
            state={note.trim() ? "done" : scene ? "active" : "waiting"}
          >
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={4}
              placeholder="例: 昼食の配膳が遅れたとき、大きな声を出して席を立った。"
              className="text-base"
            />
          </StepSection>

          <StepSection
            step={5}
            title="職員はどう対応しましたか"
            state={
              action.trim() || effectiveness
                ? "done"
                : note.trim()
                  ? "active"
                  : "waiting"
            }
            optional
          >
            <div className="space-y-3">
              <Textarea
                value={action}
                onChange={(e) => setAction(e.target.value)}
                rows={2}
                placeholder="例: 静かな部屋に移動して、落ち着くまでそばで待った。"
                className="text-base"
              />
              <div className="flex flex-wrap gap-2">
                {EFFECTIVENESS.map((ef) => (
                  <button
                    key={ef.value}
                    type="button"
                    onClick={() =>
                      setEffectiveness(effectiveness === ef.value ? "" : ef.value)
                    }
                    className={`px-4 h-11 rounded-lg border-2 text-base transition-colors ${
                      effectiveness === ef.value
                        ? "border-primary bg-primary/10 font-bold"
                        : "border-input bg-background hover:bg-muted"
                    }`}
                  >
                    {ef.label}
                  </button>
                ))}
              </div>
              <p className="text-sm text-muted-foreground">
                対応とその結果を残しておくと、「この方にはこの対応が効く」という記録が積み重なります。
              </p>
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
