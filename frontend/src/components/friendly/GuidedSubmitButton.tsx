"use client";
import { ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface Props {
  /** 未入力の項目名（空なら押せる） */
  missing: string[];
  loading: boolean;
  loadingText: string;
  onClick: () => void;
  children: ReactNode;
}

/**
 * 全幅の大きな実行ボタン。
 * 押せないときは灰色にするだけでなく、何が足りないかを日本語で示す。
 */
export function GuidedSubmitButton({ missing, loading, loadingText, onClick, children }: Props) {
  const disabled = missing.length > 0 || loading;
  return (
    <div className="space-y-2">
      <Button
        onClick={onClick}
        disabled={disabled}
        className="w-full h-14 text-lg font-bold"
      >
        {loading ? loadingText : children}
      </Button>
      {missing.length > 0 && !loading && (
        <p className="text-sm text-muted-foreground text-center" role="status">
          あと{missing.map((m) => `「${m}」`).join("と")}を済ませると押せます
        </p>
      )}
    </div>
  );
}
