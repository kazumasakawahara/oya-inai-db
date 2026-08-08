"use client";
import { useCallback, useEffect, useRef, useState } from "react";

// ------------------------------------------------------------------
// TypeScript 型宣言: Web Speech API
// ------------------------------------------------------------------
interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  readonly length: number;
  readonly isFinal: boolean;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
  readonly message: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognition;
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

// ------------------------------------------------------------------
// 無音タイムアウト（ミリ秒）
// ------------------------------------------------------------------
const SILENCE_TIMEOUT_MS = 5000;

// ブラウザ対応チェック（レンダー外で一度だけ評価）
const isBrowserSupported =
  typeof window !== "undefined" &&
  !!(window.SpeechRecognition || window.webkitSpeechRecognition);

export function useSpeechRecognition() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 確定済みテキストを ref で保持（onresult 内で最新値を参照するため）
  const finalTextRef = useRef("");

  // ------------------------------------------------------------------
  // 無音タイマーのリセット
  // ------------------------------------------------------------------
  const resetSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
    }
    silenceTimerRef.current = setTimeout(() => {
      // 5 秒間新しい結果がなければ自動停止
      recognitionRef.current?.stop();
    }, SILENCE_TIMEOUT_MS);
  }, []);

  // ------------------------------------------------------------------
  // クリーンアップ
  // ------------------------------------------------------------------
  useEffect(() => {
    return () => {
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      recognitionRef.current?.abort();
    };
  }, []);

  // ------------------------------------------------------------------
  // 録音開始
  // ------------------------------------------------------------------
  const startListening = useCallback(() => {
    if (!isBrowserSupported) return;

    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Ctor) return;

    const recognition = new Ctor();
    recognition.lang = "ja-JP";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      resetSilenceTimer();

      let finalPart = "";
      let interimPart = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalPart += result[0].transcript;
        } else {
          interimPart += result[0].transcript;
        }
      }

      if (finalPart) {
        finalTextRef.current += finalPart;
        setTranscript(finalTextRef.current);
      }
      setInterimTranscript(interimPart);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      // "aborted" はユーザー操作による停止なので無視
      if (event.error !== "aborted") {
        console.warn("SpeechRecognition error:", event.error, event.message);
      }
      setIsListening(false);
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    };

    recognition.onend = () => {
      setIsListening(false);
      setInterimTranscript("");
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    };

    recognitionRef.current = recognition;
    finalTextRef.current = "";
    setTranscript("");
    setInterimTranscript("");
    setIsListening(true);

    try {
      recognition.start();
      resetSilenceTimer();
    } catch (e) {
      console.error("SpeechRecognition start failed:", e);
      setIsListening(false);
    }
  }, [resetSilenceTimer]);

  // ------------------------------------------------------------------
  // 録音停止
  // ------------------------------------------------------------------
  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
  }, []);

  // ------------------------------------------------------------------
  // テキストリセット
  // ------------------------------------------------------------------
  const resetTranscript = useCallback(() => {
    finalTextRef.current = "";
    setTranscript("");
    setInterimTranscript("");
  }, []);

  return {
    isSupported: isBrowserSupported,
    isListening,
    transcript,
    interimTranscript,
    startListening,
    stopListening,
    resetTranscript,
  };
}
