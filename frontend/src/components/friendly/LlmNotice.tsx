"use client";
import Link from "next/link";
import { Info } from "lucide-react";

interface Props {
  /** 例: 文字起こし、AI抽出 */
  feature: string;
  /** 例: 音声の保存はできます */
  fallback?: string;
}

/**
 * LLM未設定時の事前案内。実行して初めてエラーになるのではなく、
 * 操作の前に「この機能には設定が必要」と分かるようにする。
 */
export function LlmNotice({ feature, fallback }: Props) {
  return (
    <div className="rounded-lg border-2 border-blue-300 bg-blue-50 dark:bg-blue-950/30 p-4 flex items-start gap-3">
      <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
      <p className="text-sm">
        {feature}を使うにはAIの設定が必要です
        {fallback && <>（{fallback}）</>}。
        <Link href="/settings" className="text-primary underline ml-1">
          LLM設定を開く
        </Link>
      </p>
    </div>
  );
}
