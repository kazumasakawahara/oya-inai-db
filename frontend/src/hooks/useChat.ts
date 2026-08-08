"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { IntakeProgress, IntakePreview, ModelSwitchInfo } from "@/lib/types";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface AgentInfo {
  agent: string;
  decision: string;
}

/** WebSocket 再接続の最大リトライ回数 */
const MAX_RECONNECT_ATTEMPTS = 3;

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [agentInfo, setAgentInfo] = useState<AgentInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [intakeProgress, setIntakeProgress] = useState<IntakeProgress[]>([]);
  const [intakePreview, setIntakePreview] = useState<IntakePreview | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelSwitchInfo | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const currentResponseRef = useRef("");
  const reconnectCountRef = useRef(0);

  // ----------------------------------------------------------------
  // 共通: WebSocket メッセージ処理（JSON.parse を try/catch で保護）
  // ----------------------------------------------------------------
  const handleWsMessage = useCallback((event: MessageEvent) => {
    let msg: {
      type?: string;
      content?: string;
      agent?: string;
      decision?: string;
      phase?: number;
      total?: number;
      pillar?: string;
      status?: "pending" | "active" | "complete";
      nodes?: IntakePreview["nodes"];
      relationships?: IntakePreview["relationships"];
      registered_count?: number;
      provider?: string;
      model?: string;
    };
    try {
      msg = JSON.parse(event.data);
    } catch {
      console.warn("WebSocket: 不正な JSON を受信:", event.data);
      return; // 壊れたメッセージは無視
    }

    if (msg.type === "routing") {
      setAgentInfo({ agent: msg.agent ?? "", decision: msg.decision ?? "" });
    } else if (msg.type === "stream") {
      currentResponseRef.current += msg.content || "";
      const text = currentResponseRef.current;
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant") {
          return [...prev.slice(0, -1), { role: "assistant", content: text }];
        }
        return [...prev, { role: "assistant", content: text }];
      });
    } else if (msg.type === "done") {
      currentResponseRef.current = "";
      setIsLoading(false);
      setAgentInfo(null);
    } else if (msg.type === "error") {
      // サーバー側から返されるエラーメッセージ
      setError(msg.content || "サーバーエラーが発生しました");
      setIsLoading(false);
    } else if (msg.type === "intake_progress") {
      // インテーク進捗更新
      const progress: IntakeProgress = {
        phase: msg.phase ?? 0,
        total: msg.total ?? 7,
        pillar: msg.pillar ?? "",
        status: msg.status ?? "pending",
      };
      setIntakeProgress((prev) => {
        const idx = prev.findIndex((p) => p.pillar === progress.pillar);
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = progress;
          return updated;
        }
        return [...prev, progress];
      });
    } else if (msg.type === "intake_preview") {
      // 抽出ノードのプレビュー
      setIntakePreview({
        nodes: msg.nodes ?? [],
        relationships: msg.relationships ?? [],
      });
    } else if (msg.type === "intake_complete") {
      // インテーク完了
      const count = msg.registered_count ?? 0;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `登録完了: ${count}件のノードを登録しました。` },
      ]);
      setIsLoading(false);
    } else if (msg.type === "model_switched") {
      setModelInfo({
        provider: msg.provider ?? "",
        model: msg.model ?? "",
      });
    }
  }, []);

  // ----------------------------------------------------------------
  // 共通: WebSocket close/error ハンドラ
  // ----------------------------------------------------------------
  const handleWsClose = useCallback(() => {
    console.log("Chat WebSocket closed");
    wsRef.current = null;
    setIsLoading(false);
  }, []);

  const handleWsError = useCallback(() => {
    console.warn("Chat WebSocket error");
    wsRef.current = null;
    setIsLoading(false);
  }, []);

  // ----------------------------------------------------------------
  // WebSocket 初期化（ページロード時に1回だけ）
  // ----------------------------------------------------------------
  useEffect(() => {
    const apiBase =
      (typeof window !== "undefined" &&
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (window as any).__NEXT_DATA__?.runtimeConfig?.NEXT_PUBLIC_API_URL) ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8001";
    const wsUrl = apiBase.replace(/^http/, "ws") + "/api/chat/ws";

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => {
        console.log("Chat WebSocket connected");
        reconnectCountRef.current = 0;
        setError(null);
      };
      ws.onmessage = handleWsMessage;
      ws.onclose = handleWsClose;
      ws.onerror = handleWsError;

      return () => {
        ws.close();
      };
    } catch (e) {
      console.error("WebSocket の初期化に失敗:", e);
      setError("チャットサーバーに接続できませんでした");
      return undefined;
    }
  }, [handleWsMessage, handleWsClose, handleWsError]);

  // ----------------------------------------------------------------
  // メッセージ送信（切断時は再接続を試みる）
  // ----------------------------------------------------------------
  const sendMessage = useCallback(
    (content: string, mode?: "chat" | "intake") => {
      setError(null);
      setMessages((prev) => [...prev, { role: "user", content }]);
      setIsLoading(true);
      currentResponseRef.current = "";

      const payload = JSON.stringify({ type: "message", content, mode: mode ?? "chat" });

      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(payload);
        return;
      }

      // --- 再接続 ---
      if (reconnectCountRef.current >= MAX_RECONNECT_ATTEMPTS) {
        setError("チャットサーバーとの接続が切れました。ページを再読み込みしてください。");
        setIsLoading(false);
        return;
      }
      reconnectCountRef.current += 1;

      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
      const wsUrl = apiBase.replace(/^http/, "ws") + "/api/chat/ws";

      try {
        const newWs = new WebSocket(wsUrl);
        wsRef.current = newWs;

        newWs.onopen = () => {
          reconnectCountRef.current = 0;
          setError(null);
          newWs.send(payload);
        };
        newWs.onmessage = handleWsMessage;
        newWs.onclose = handleWsClose;
        newWs.onerror = () => {
          handleWsError();
          setError("チャットサーバーに再接続できませんでした");
        };
      } catch (e) {
        console.error("WebSocket 再接続失敗:", e);
        setError("チャットサーバーに再接続できませんでした");
        setIsLoading(false);
      }
    },
    [handleWsMessage, handleWsClose, handleWsError],
  );

  /** エラー状態をクリアする */
  const clearError = useCallback(() => setError(null), []);

  return {
    messages,
    isLoading,
    agentInfo,
    error,
    sendMessage,
    clearError,
    intakeProgress,
    intakePreview,
    modelInfo,
  };
}
