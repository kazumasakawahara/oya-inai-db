"use client";
import { CheckCircle2, XCircle } from "lucide-react";

interface Props {
  kind: "success" | "error";
  message: string;
  /** 失敗時に「次にどうすればよいか」を1文で */
  action?: string;
}

/**
 * 大きな結果表示帯。英語ステータスは使わず日本語の文章で伝える。
 */
export function ResultBanner({ kind, message, action }: Props) {
  const ok = kind === "success";
  return (
    <div
      role="status"
      className={`rounded-lg border-2 p-4 flex items-start gap-3 ${
        ok
          ? "border-green-500 bg-green-50 dark:bg-green-950/30"
          : "border-red-500 bg-red-50 dark:bg-red-950/30"
      }`}
    >
      {ok ? (
        <CheckCircle2 className="w-6 h-6 text-green-600 shrink-0 mt-0.5" />
      ) : (
        <XCircle className="w-6 h-6 text-red-600 shrink-0 mt-0.5" />
      )}
      <div>
        <p className="text-base font-bold">{message}</p>
        {action && <p className="text-sm text-muted-foreground mt-1">{action}</p>}
      </div>
    </div>
  );
}
