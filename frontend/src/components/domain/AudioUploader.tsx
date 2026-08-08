"use client";
import { useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

const ACCEPTED = ".mp3,.wav,.m4a,.ogg,.flac,.aac,.webm";

interface Props {
  clients: { name: string }[];
  onUploaded?: () => void;
}

export function AudioUploader({ clients, onUploaded }: Props) {
  const [selectedClient, setSelectedClient] = useState("");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ status: string; transcript?: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file || !selectedClient) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await api.meetings.upload(file, selectedClient, title, note);
      setResult(res);
      onUploaded?.();
      setTitle("");
      setNote("");
      if (fileRef.current) fileRef.current.value = "";
    } catch (e) {
      setResult({ status: "error", transcript: String(e) });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">音声ファイルをアップロード</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <label className="text-sm font-medium mb-1 block">クライアント</label>
          <select
            value={selectedClient}
            onChange={(e) => setSelectedClient(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
          >
            <option value="">選択してください</option>
            {clients.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-sm font-medium mb-1 block">音声ファイル</label>
          <input ref={fileRef} type="file" accept={ACCEPTED} className="text-sm" />
          <p className="text-xs text-muted-foreground mt-1">
            対応形式: MP3, WAV, M4A, OGG, FLAC, AAC, WebM
          </p>
        </div>
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="タイトル（任意）"
        />
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="メモ（任意）"
          rows={2}
        />
        <Button onClick={handleUpload} disabled={!selectedClient || loading}>
          {loading ? "アップロード・文字起こし中..." : "アップロード"}
        </Button>
        {result && (
          <div className="mt-3">
            <Badge variant={result.status === "success" ? "default" : "destructive"}>
              {result.status}
            </Badge>
            {result.transcript && (
              <div className="mt-2 p-3 bg-muted rounded text-sm max-h-48 overflow-y-auto">
                <p className="font-medium mb-1">文字起こし結果:</p>
                <p className="whitespace-pre-wrap">{result.transcript}</p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
