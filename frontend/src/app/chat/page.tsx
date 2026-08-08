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

export default function ChatPage() {
  const { messages, isLoading, agentInfo, error, sendMessage, clearError } = useChat();
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

  // 初回表示時に入力欄にフォーカス
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // 音声認識中はフックの値を表示、それ以外は手入力値を表示
  const displayValue = isListening
    ? transcript + interimTranscript
    : transcript || input;

  const handleSend = () => {
    const text = displayValue.trim();
    if (!text) return;
    if (isListening) stopListening();
    sendMessage(text);
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

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)]">
      <h2 className="text-2xl font-bold mb-4">AIチャット</h2>

      {/* Agent Status */}
      {agentInfo && (
        <div className="mb-2 flex items-center gap-2">
          <Badge variant="secondary">{agentInfo.agent}</Badge>
          <span className="text-sm text-muted-foreground">{agentInfo.decision}</span>
          {isLoading && <span className="text-sm animate-pulse">処理中...</span>}
        </div>
      )}

      {/* メッセージがない場合: 入力欄を中央に目立たせる */}
      {isEmpty ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-6 -mt-16">
          <div className="text-center">
            <p className="text-3xl mb-2">💬</p>
            <h3 className="text-lg font-semibold text-foreground">支援情報を検索できます</h3>
            <p className="text-sm text-muted-foreground mt-1">
              クライアント名を含めて質問してください
            </p>
          </div>

          {/* 入力欄（中央配置・大きめ） */}
          <Card className="w-full max-w-2xl border-2 shadow-md">
            <CardContent className="p-4">
              {error && (
                <div className="mb-3 flex items-center gap-2">
                  <p className="text-sm text-destructive flex-1">{error}</p>
                  <Button variant="ghost" size="sm" onClick={clearError}>✕</Button>
                </div>
              )}
              <div className="flex gap-2">
                <Input
                  ref={inputRef}
                  value={displayValue}
                  onChange={(e) => { resetTranscript(); setInput(e.target.value); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) handleSend(); }}
                  placeholder="例: 山田健太さんの緊急連絡先を教えてください"
                  disabled={isLoading}
                  className="h-12 text-base"
                />
                {micSupported && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleMic}
                    className={`h-12 w-12 shrink-0 ${isListening ? "animate-pulse text-red-500" : ""}`}
                    aria-label={isListening ? "音声入力を停止" : "音声入力を開始"}
                  >
                    {isListening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                  </Button>
                )}
                <Button onClick={handleSend} disabled={isLoading || !displayValue.trim()} className="h-12 px-6">
                  送信
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* クイックアクション */}
          <div className="flex flex-wrap gap-2 max-w-2xl justify-center">
            {[
              "更新期限が近い手帳を確認して",
              "山田健太さんの基本情報",
              "佐藤花子さんの支援記録を見せて",
            ].map((q) => (
              <Button
                key={q}
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => { setInput(q); inputRef.current?.focus(); }}
              >
                {q}
              </Button>
            ))}
          </div>
        </div>
      ) : (
        /* メッセージがある場合: 従来のチャット表示 */
        <>
          <ScrollArea className="flex-1 mb-4">
            <div className="space-y-3 pr-4">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <Card className={`max-w-[80%] ${msg.role === "user" ? "bg-primary text-primary-foreground" : ""}`}>
                    <CardContent className="p-3">
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </CardContent>
                  </Card>
                </div>
              ))}
              {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
                <div className="flex justify-start">
                  <Card><CardContent className="p-3"><p className="text-sm animate-pulse">考え中...</p></CardContent></Card>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>

          {/* Error */}
          {error && (
            <div className="mb-2 flex items-center gap-2">
              <p className="text-sm text-destructive flex-1">{error}</p>
              <Button variant="ghost" size="sm" onClick={clearError}>✕</Button>
            </div>
          )}

          {/* 入力欄（下部固定・カードで囲む） */}
          <Card className="border-2 shadow-sm">
            <CardContent className="p-3">
              <div className="flex gap-2">
                <Input
                  ref={inputRef}
                  value={displayValue}
                  onChange={(e) => { resetTranscript(); setInput(e.target.value); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) handleSend(); }}
                  placeholder="メッセージを入力..."
                  disabled={isLoading}
                  className="h-11 text-base"
                />
                {micSupported && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={toggleMic}
                    className={`h-11 w-11 shrink-0 ${isListening ? "animate-pulse text-red-500" : ""}`}
                    aria-label={isListening ? "音声入力を停止" : "音声入力を開始"}
                  >
                    {isListening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                  </Button>
                )}
                <Button onClick={handleSend} disabled={isLoading || !displayValue.trim()} className="h-11 px-6">
                  送信
                </Button>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
