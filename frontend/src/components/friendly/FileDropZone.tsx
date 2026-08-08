"use client";
import { useRef, useState, DragEvent } from "react";
import { Music, FileUp, Check } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  accept: string;
  file: File | null;
  onSelect: (file: File | null) => void;
  /** 枠内に出す補足（例: スマホの録音アプリのファイルがそのまま使えます） */
  hint?: string;
  /** アイコン種別 */
  kind?: "audio" | "document";
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/**
 * 大きなクリック/ドラッグ&ドロップ対応のファイル選択枠。
 * 素の <input type="file"> を置き換える。
 */
export function FileDropZone({ accept, file, onSelect, hint, kind = "audio" }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const Icon = kind === "audio" ? Music : FileUp;

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) onSelect(dropped);
  };

  if (file) {
    return (
      <div className="border-2 border-green-500 rounded-lg p-4 bg-green-50/50 dark:bg-green-950/20 flex items-center gap-3">
        <Check className="w-6 h-6 text-green-600 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-base font-medium truncate">
            <Icon className="w-4 h-4 inline mr-1" />
            {file.name}
          </p>
          <p className="text-sm text-muted-foreground">
            {formatSize(file.size)} — 選べました
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            onSelect(null);
            if (inputRef.current) inputRef.current.value = "";
            inputRef.current?.click();
          }}
        >
          選び直す
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => onSelect(e.target.files?.[0] ?? null)}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`w-full border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer ${
        dragging
          ? "border-primary bg-primary/5"
          : "border-muted-foreground/40 hover:border-primary hover:bg-muted/50"
      }`}
    >
      <Icon className="w-10 h-10 mx-auto mb-2 text-muted-foreground" />
      <p className="text-base font-bold">ここを押してファイルを選ぶ</p>
      <p className="text-sm text-muted-foreground mt-1">
        （パソコンからファイルをここへドラッグしても選べます）
      </p>
      {hint && <p className="text-sm text-muted-foreground mt-2">{hint}</p>}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onSelect(e.target.files?.[0] ?? null)}
      />
    </button>
  );
}
