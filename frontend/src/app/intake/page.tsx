"use client";
import { useState, useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Mic, MicOff } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

// ------------------------------------------------------------------
// 7 Pillars（マニフェスト v4.0）
// ------------------------------------------------------------------
const PILLARS = [
  { id: 1, label: "本人性（Identity）", description: "名前・生年月日・血液型" },
  { id: 2, label: "ケアの暗黙知", description: "禁忌事項・推奨ケア" },
  { id: 3, label: "安全ネット", description: "緊急連絡先・病院" },
  { id: 4, label: "法的基盤", description: "手帳・後見人" },
  { id: 5, label: "親の機能移行", description: "親の健康・役割" },
  { id: 6, label: "金銭的安全", description: "金銭管理" },
  { id: 7, label: "多機関連携", description: "利用サービス" },
] as const;

type PillarStatus = "pending" | "active" | "complete";

export default function IntakePage() {
  const {
    messages,
    isLoading,
    agentInfo,
    error,
    sendMessage,
    clearError,
    intakeProgress,
    intakePreview,
    modelInfo,
  } = useChat();

  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const {
    isSupported: micSupported,
    isListening,
    transcript,
    interimTranscript,
    startListening,
    stopListening,
    resetTranscript,
  } = useSpeechRecognition();

  // メッセージ追加時に自動スクロール
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // 初回フォーカス
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // 音声認識中はフックの値を表示、それ以外は手入力値を表示
  const displayValue = isListening
    ? transcript + interimTranscript
    : transcript || input;

  // ------------------------------------------------------------------
  // Pillar ステータスの算出
  // ------------------------------------------------------------------
  const getPillarStatus = (pillarLabel: string): PillarStatus => {
    const match = intakeProgress.find((p) => p.pillar === pillarLabel);
    return match?.status ?? "pending";
  };

  // 現在アクティブなフェーズ番号（進捗から算出）
  const activePhase = (() => {
    const active = intakeProgress.find((p) => p.status === "active");
    if (active) return active.phase;
    const completed = intakeProgress.filter((p) => p.status === "complete");
    return completed.length > 0 ? completed.length + 1 : 1;
  })();

  // ------------------------------------------------------------------
  // ハンドラ
  // ------------------------------------------------------------------
  const handleSend = () => {
    const text = displayValue.trim();
    if (!text) return;
    if (isListening) stopListening();
    sendMessage(text, "intake");
    setInput("");
    resetTranscript();
    inputRef.current?.focus();
  };

  const toggleMic = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  // ------------------------------------------------------------------
  // ステータスバッジのスタイル
  // ------------------------------------------------------------------
  const statusBadge = (status: PillarStatus) => {
    switch (status) {
      case "complete":
        return <Badge className="bg-green-600 text-white text-xs">完了</Badge>;
      case "active":
        return <Badge className="bg-blue-600 text-white text-xs animate-pulse">進行中</Badge>;
      default:
        return <Badge variant="secondary" className="text-xs">未着手</Badge>;
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)]">
      {/* ヘッダー */}
      <div className="mb-4 flex items-center gap-4">
        <h2 className="text-2xl font-bold">新規インテーク</h2>
        <Badge variant="outline" className="text-sm">
          フェーズ {activePhase} / {PILLARS.length}
        </Badge>
        {modelInfo && (
          <Badge variant="secondary" className="text-xs">
            {modelInfo.provider}: {modelInfo.model}
          </Badge>
        )}
      </div>

      {/* Agent Status */}
      {agentInfo && (
        <div className="mb-2 flex items-center gap-2">
          <Badge variant="secondary">{agentInfo.agent}</Badge>
          <span className="text-sm text-muted-foreground">{agentInfo.decision}</span>
          {isLoading && <span className="text-sm animate-pulse">処理中...</span>}
        </div>
      )}

      {/* メインレイアウト: サイドバー + チャット */}
      <div className="flex flex-1 gap-4 min-h-0">
        {/* 左カラム: 7 Pillars 進捗 */}
        <Card className="w-64 shrink-0">
          <CardContent className="p-3">
            <p className="text-sm font-semibold mb-3 text-muted-foreground">7つの柱</p>
            <div className="space-y-2">
              {PILLARS.map((pillar) => {
                const status = getPillarStatus(pillar.label);
                return (
                  <div
                    key={pillar.id}
                    className={`rounded-md border p-2 text-sm ${
                      status === "active"
                        ? "border-blue-400 bg-blue-50 dark:bg-blue-950"
                        : status === "complete"
                          ? "border-green-400 bg-green-50 dark:bg-green-950"
                          : "border-border"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-medium text-xs">
                        {pillar.id}. {pillar.label}
                      </span>
                      {statusBadge(status)}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {pillar.description}
                    </p>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* 右カラム: チャット + プレビュー */}
        <div className="flex-1 flex flex-col min-h-0">
          {/* 抽出ノードプレビュー */}
          {intakePreview && intakePreview.nodes.length > 0 && (
            <Card className="mb-3 border-dashed">
              <CardContent className="p-3">
                <p className="text-xs font-semibold text-muted-foreground mb-2">
                  抽出ノード（プレビュー）
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {intakePreview.nodes.map((node) => (
                    <Badge key={node.temp_id} variant="outline" className="text-xs">
                      {node.label}
                      {node.properties.name
                        ? `: ${String(node.properties.name)}`
                        : node.properties.action
                          ? `: ${String(node.properties.action)}`
                          : ""}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* チャットメッセージ */}
          <ScrollArea className="flex-1 mb-3">
            <div className="space-y-3 pr-4">
              {messages.length === 0 && (
                <div className="flex items-center justify-center h-32 text-muted-foreground">
                  <p className="text-sm">
                    利用者について知っていることを自由にお話しください。音声入力もできます。
                  </p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <Card
                    className={`max-w-[80%] ${
                      msg.role === "user" ? "bg-primary text-primary-foreground" : ""
                    }`}
                  >
                    <CardContent className="p-3">
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </CardContent>
                  </Card>
                </div>
              ))}
              {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
                <div className="flex justify-start">
                  <Card>
                    <CardContent className="p-3">
                      <p className="text-sm animate-pulse">考え中...</p>
                    </CardContent>
                  </Card>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>

          {/* エラー */}
          {error && (
            <div className="mb-2 flex items-center gap-2">
              <p className="text-sm text-destructive flex-1">{error}</p>
              <Button variant="ghost" size="sm" onClick={clearError}>
                ✕
              </Button>
            </div>
          )}

          {/* 入力欄 */}
          <Card className="border-2 shadow-sm">
            <CardContent className="p-3">
              <div className="flex gap-2">
                <Input
                  ref={inputRef}
                  value={displayValue}
                  onChange={(e) => { resetTranscript(); setInput(e.target.value); }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.nativeEvent.isComposing) handleSend();
                  }}
                  placeholder="利用者の情報を入力してください..."
                  disabled={isLoading}
                  className="h-12 text-base"
                />
                {micSupported && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleMic}
                    className={`h-12 w-12 shrink-0 ${
                      isListening ? "animate-pulse text-red-500" : ""
                    }`}
                    aria-label={isListening ? "音声入力を停止" : "音声入力を開始"}
                  >
                    {isListening ? (
                      <MicOff className="h-5 w-5" />
                    ) : (
                      <Mic className="h-5 w-5" />
                    )}
                  </Button>
                )}
                <Button
                  onClick={handleSend}
                  disabled={isLoading || !displayValue.trim()}
                  className="h-12 px-6"
                >
                  送信
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
