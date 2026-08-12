"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { StepSection } from "@/components/friendly/StepSection";
import { ClientPicker } from "@/components/friendly/ClientPicker";
import { FileDropZone } from "@/components/friendly/FileDropZone";
import { GuidedSubmitButton } from "@/components/friendly/GuidedSubmitButton";
import { ResultBanner } from "@/components/friendly/ResultBanner";
import { api } from "@/lib/api";

const DOCUMENT_ACCEPTED = ".docx,.xlsx,.pdf,.txt";

// 2026-08-12: 音声モードは廃止（AI を Claude 一本にまとめる方針。Claude は音声を扱えない）
type Mode = "text" | "document";

const MODES: { value: Mode; emoji: string; label: string; description: string }[] = [
  { value: "text", emoji: "✍️", label: "その場で文字で入力", description: "この画面に直接書きます" },
  { value: "document", emoji: "📄", label: "文書ファイルを添付", description: "Word・PDF・テキストなど" },
];

interface Props {
  clients: { name: string }[];
  clientsError?: boolean;
  onUploaded?: () => void;
}

export function MeetingRecordForm({ clients, clientsError, onUploaded }: Props) {
  const [selectedClient, setSelectedClient] = useState("");
  const [mode, setMode] = useState<Mode | "">("");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message?: string; transcript?: string } | null>(null);

  const contentReady =
    mode === "text" ? !!text.trim() : mode === "" ? false : !!file;

  const missing: string[] = [];
  if (!selectedClient) missing.push("① 利用者を選ぶ");
  if (!mode) missing.push("② 記録のかたちを選ぶ");
  else if (!contentReady) {
    missing.push(
      mode === "text"
        ? "③ 面談の内容を書く"
        : "③ 文書ファイルを選ぶ"
    );
  }

  const selectMode = (m: Mode) => {
    setMode(m);
    setFile(null);
  };

  const handleSubmit = async () => {
    if (missing.length > 0) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await api.meetings.upload({
        clientName: selectedClient,
        file: mode === "text" ? undefined : (file ?? undefined),
        text: mode === "text" ? text : undefined,
        title,
        note,
      });
      setResult({
        ok: res.status === "success",
        message: res.message,
        transcript: mode === "text" ? undefined : res.transcript,
      });
      if (res.status === "success") {
        onUploaded?.();
        setTitle("");
        setNote("");
        setFile(null);
        setText("");
      }
    } catch {
      setResult({ ok: false });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">面談を記録する</CardTitle>
        <p className="text-sm text-muted-foreground">
          上から順番に①→②→③と進めてください。
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <StepSection
          step={1}
          title="利用者を選ぶ"
          state={selectedClient ? "done" : "active"}
        >
          <ClientPicker
            clients={clients}
            value={selectedClient}
            onChange={setSelectedClient}
            loadError={clientsError}
          />
        </StepSection>

        <StepSection
          step={2}
          title="記録のかたちを選ぶ"
          state={mode ? "done" : selectedClient ? "active" : "waiting"}
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => selectMode(m.value)}
                className={`flex flex-col items-center gap-1 p-4 rounded-lg border-2 text-center transition-colors ${
                  mode === m.value
                    ? "border-primary bg-primary/10 font-bold"
                    : "border-input bg-background hover:bg-muted"
                }`}
              >
                <span className="text-3xl">{m.emoji}</span>
                <span className="text-base">{m.label}</span>
                <span className="text-xs text-muted-foreground font-normal">
                  {m.description}
                </span>
              </button>
            ))}
          </div>
        </StepSection>

        {mode === "text" && (
          <StepSection
            step={3}
            title="面談の内容を書く"
            state={text.trim() ? "done" : "active"}
          >
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              placeholder={"例: 4月10日、ご本人・お母様と面談。\n最近の体調、日中活動の様子、今後の希望について話した。"}
              className="text-base"
            />
          </StepSection>
        )}

        {mode === "document" && (
          <StepSection
            step={3}
            title="文書ファイルを選ぶ"
            state={file ? "done" : "active"}
          >
            <FileDropZone
              accept={DOCUMENT_ACCEPTED}
              file={file}
              onSelect={setFile}
              hint="面談の記録が書かれた Word・Excel・PDF・テキストファイルが使えます。中の文章を自動で読み取って保存します"
              kind="document"
            />
          </StepSection>
        )}

        <StepSection
          step={4}
          title="タイトルとメモ"
          state={title || note ? "done" : contentReady ? "active" : "waiting"}
          optional
        >
          <div className="space-y-3">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例: 4月の定期面談"
              className="h-12 text-base"
            />
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="例: ご家族も同席。次回は6月ごろ。"
              rows={2}
              className="text-base"
            />
          </div>
        </StepSection>

        <GuidedSubmitButton
          missing={missing}
          loading={loading}
          loadingText="保存しています…"
          onClick={handleSubmit}
        >
          記録を保存する
        </GuidedSubmitButton>

        {result && (
          <div className="space-y-3">
            <ResultBanner
              kind={result.ok ? "success" : "error"}
              message={result.ok ? "記録を保存できました。" : "保存できませんでした。"}
              action={
                result.ok
                  ? undefined
                  : result.message ||
                    "インターネット接続を確認して、もう一度「記録を保存する」を押してください。"
              }
            />
            {result.transcript && (
              <div className="p-3 bg-muted rounded-lg text-base max-h-48 overflow-y-auto">
                <p className="font-bold mb-1">読み取った内容:</p>
                <p className="whitespace-pre-wrap">{result.transcript}</p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
