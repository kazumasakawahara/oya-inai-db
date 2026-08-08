"use client";
import Link from "next/link";

interface Props {
  clients: { name: string }[];
  value: string;
  onChange: (name: string) => void;
  loadError?: boolean;
}

/**
 * 大きなクライアント選択。
 * 0件時は登録ページへの案内を出す。
 */
export function ClientPicker({ clients, value, onChange, loadError }: Props) {
  if (loadError) {
    return (
      <p className="text-base text-destructive">
        利用者の一覧を読み込めませんでした。ページを再読み込みしてもう一度お試しください。
      </p>
    );
  }
  if (clients.length === 0) {
    return (
      <p className="text-base text-muted-foreground">
        まだ利用者が登録されていません。先に
        <Link href="/clients" className="text-primary underline mx-1">
          クライアント一覧
        </Link>
        から登録してください。
      </p>
    );
  }
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full h-12 border-2 rounded-lg px-3 text-lg bg-background"
      aria-label="利用者を選ぶ"
    >
      <option value="">▼ 押して利用者を選ぶ</option>
      {clients.map((c) => (
        <option key={c.name} value={c.name}>
          {c.name}
        </option>
      ))}
    </select>
  );
}
