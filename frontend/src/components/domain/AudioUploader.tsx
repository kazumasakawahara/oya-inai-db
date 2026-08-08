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
import { LlmNotice } from "@/components/friendly/LlmNotice";
import { api } from "@/lib/api";

const ACCEPTED = ".mp3,.wav,.m4a,.ogg,.flac,.aac,.webm";

interface Props {
  clients: { name: string }[];
  clientsError?: boolean;
  onUploaded?: () => void;
}

export function AudioUploader({ clients, clientsError, onUploaded }: Props) {
  const [selectedClient, setSelectedClient] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; transcript?: string } | null>(null);

  const { data: systemStatus } = useQuery({
    queryKey: ["system-status"],
    queryFn: () => api.system.status(),
    retry: 1,
  });
  const transcriptionReady = systemStatus?.gemini_available ?? true;

  const missing: string[] = [];
  if (!selectedClient) missing.push("① 利用者を選ぶ");
  if (!file) missing.push("② 音声ファイルを選ぶ");

  const handleUpload = async () => {
    if (!file || !selectedClient) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await api.meetings.upload(file, selectedClient, title, note);
      setResult({ ok: res.status === "success", transcript: res.transcript });
      if (res.status === "success") {
        onUploaded?.();
        setTitle("");
        setNote("");
        setFile(null);
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
        <CardTitle className="text-lg">音声ファイルをアップロード</CardTitle>
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
          title="音声ファイルを選ぶ"
          state={file ? "done" : selectedClient ? "active" : "waiting"}
        >
          <div className="space-y-3">
            {!transcriptionReady && (
              <LlmNotice feature="文字起こし" fallback="音声の保存はできます" />
            )}
            <FileDropZone
              accept={ACCEPTED}
              file={file}
              onSelect={setFile}
              hint="スマホの録音アプリで録った音声ファイルがそのまま使えます（MP3・WAV・M4Aなど）"
              kind="audio"
            />
          </div>
        </StepSection>

        <StepSection
          step={3}
          title="タイトルとメモ"
          state={title || note ? "done" : file && selectedClient ? "active" : "waiting"}
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
          loadingText="アップロード中…（数分かかることがあります。このまま待っていてください）"
          onClick={handleUpload}
        >
          アップロードする
        </GuidedSubmitButton>

        {result && (
          <div className="space-y-3">
            <ResultBanner
              kind={result.ok ? "success" : "error"}
              message={
                result.ok
                  ? "アップロードできました。"
                  : "アップロードできませんでした。"
              }
              action={
                result.ok
                  ? undefined
                  : "インターネット接続を確認して、もう一度「アップロードする」を押してください。"
              }
            />
            {result.transcript && (
              <div className="p-3 bg-muted rounded-lg text-base max-h-48 overflow-y-auto">
                <p className="font-bold mb-1">文字起こし結果:</p>
                <p className="whitespace-pre-wrap">{result.transcript}</p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
