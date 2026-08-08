"use client";
import { useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import type { ExtractedGraph } from "@/lib/types";

interface SemanticWarning {
  label: string;
  new_text: string;
  existing_text: string;
  similarity_score: number;
}

interface NarrativeRegisterResult {
  status: string;
  registered_count?: number;
  message?: string;
}

function _stageLabel(stage: string): string {
  const labels: Record<string, string> = {
    started: "準備中",
    chunking: "テキスト解析",
    extracting: "AI抽出",
    validating: "構造検証",
    dedup_check: "重複チェック",
    complete: "完了",
    error: "エラー",
  };
  return labels[stage] || stage;
}

const ACCEPTED_EXTENSIONS = ".docx,.xlsx,.pdf,.txt";

export default function NarrativePage() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [text, setText] = useState("");
  const [extractedData, setExtractedData] = useState<ExtractedGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [progress, setProgress] = useState<{
    stage: string;
    progress: number;
    message: string;
  } | null>(null);
  const [semanticWarnings, setSemanticWarnings] = useState<SemanticWarning[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const res = await api.narratives.upload(file);
      setText(res.text);
      setUploadedFileName(res.filename);
    } catch (err) {
      setResult(`ファイル読み込みエラー: ${err}`);
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleExtract = async () => {
    setLoading(true);
    setProgress({ stage: "started", progress: 0, message: "開始..." });
    setSemanticWarnings([]);
    try {
      await api.narratives.extractStream(text, undefined, (event) => {
        setProgress(event);
        if (event.stage === "complete" && event.data?.graph) {
          setExtractedData(event.data.graph as ExtractedGraph);
          setSemanticWarnings(
            (event.data.semanticWarnings as SemanticWarning[] | undefined) || []
          );
          setStep(2);
        }
        if (event.stage === "error") {
          setResult(`抽出エラー: ${event.message}`);
        }
      });
    } catch (err) {
      setResult(`ストリーミングエラー: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    if (!extractedData) return;
    setLoading(true);
    try {
      const res = (await api.narratives.register(extractedData)) as NarrativeRegisterResult;
      setResult(
        res.status === "success"
          ? `登録完了: ${res.registered_count}件のノードを登録しました。`
          : `エラー: ${res.message}`
      );
      setStep(3);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setStep(1);
    setText("");
    setExtractedData(null);
    setResult(null);
    setUploadedFileName(null);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">ナラティブ入力</h2>

      {/* Progress */}
      <div className="flex gap-2 items-center">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${
                step >= s
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted"
              }`}
            >
              {s}
            </div>
            <span className="text-sm">
              {s === 1 ? "入力" : s === 2 ? "確認" : "完了"}
            </span>
            {s < 3 && <div className="w-8 h-px bg-border" />}
          </div>
        ))}
      </div>

      {/* Step 1: Input */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>テキスト入力</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder="支援記録や面談メモをここに入力してください..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={10}
            />

            <Separator />

            {/* File Upload */}
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                またはファイルからテキストを読み込み（Word / Excel / PDF / テキスト）
              </p>
              <div className="flex items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPTED_EXTENSIONS}
                  onChange={handleFileUpload}
                  className="hidden"
                  id="file-upload"
                />
                <Button
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={loading}
                >
                  {loading ? "読み込み中..." : "ファイルを選択"}
                </Button>
                {uploadedFileName && (
                  <span className="text-sm text-muted-foreground">
                    {uploadedFileName}
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                対応形式: .docx, .xlsx, .pdf, .txt
              </p>
            </div>

            <Separator />

            {loading && progress && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{_stageLabel(progress.stage)}</span>
                  <span className="text-muted-foreground">{progress.progress}%</span>
                </div>
                <Progress value={progress.progress} />
                <p className="text-xs text-muted-foreground">{progress.message}</p>
              </div>
            )}

            <Button
              onClick={handleExtract}
              disabled={!text.trim() || loading}
              className="w-full"
            >
              {loading ? "処理中..." : "AI抽出を実行"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Preview */}
      {step === 2 && extractedData && (
        <Card>
          <CardHeader>
            <CardTitle>抽出プレビュー</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              ノード {extractedData.nodes.length}件 / リレーション{" "}
              {extractedData.relationships.length}件
            </p>
            <div className="space-y-2">
              {extractedData.nodes.map((node, i) => (
                <div
                  key={i}
                  className={`border rounded p-3 ${
                    node.label === "NgAction" ? "border-red-500" : ""
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Badge
                      variant={
                        node.label === "NgAction" ? "destructive" : "outline"
                      }
                    >
                      {node.label}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {node.temp_id}
                    </span>
                  </div>
                  <pre className="text-xs bg-muted p-2 rounded overflow-x-auto">
                    {JSON.stringify(node.properties, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
            {semanticWarnings.length > 0 && (
              <div className="border border-amber-500 rounded p-3 bg-amber-50">
                <p className="text-sm font-medium text-amber-900 mb-2">
                  ⚠ 類似する既存ノードが {semanticWarnings.length} 件見つかりました
                </p>
                <ul className="text-xs space-y-1">
                  {semanticWarnings.slice(0, 5).map((w, i) => (
                    <li key={i} className="text-amber-800">
                      [{w.label}] {w.new_text} ≈ {w.existing_text}
                      ({(w.similarity_score * 100).toFixed(1)}%)
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(1)}>
                戻る
              </Button>
              <Button onClick={handleRegister} disabled={loading}>
                {loading ? "登録中..." : "確認して登録"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Done */}
      {step === 3 && (
        <Card>
          <CardContent className="pt-6 text-center space-y-4">
            <p className="text-lg">{result}</p>
            <Button onClick={handleReset}>新しい入力を開始</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
