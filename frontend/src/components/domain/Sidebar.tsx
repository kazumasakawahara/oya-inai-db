"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/", label: "ホーム", section: "ホーム" },
  { href: "/intake", label: "インテーク", section: "記録" },
  { href: "/narrative", label: "ナラティブ入力", section: "記録" },
  { href: "/quicklog", label: "クイックログ", section: "記録" },
  { href: "/meetings", label: "面談記録", section: "記録" },
  { href: "/clients", label: "クライアント一覧", section: "管理" },
  { href: "/search", label: "セマンティック検索", section: "活用" },
  { href: "/ecomap", label: "エコマップ", section: "活用" },
  { href: "/graph", label: "知識グラフ", section: "活用" },
  { href: "/chat", label: "AIチャット", section: "活用" },
  { href: "/settings", label: "LLM設定", section: "設定" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: status, isError } = useQuery({
    queryKey: ["system-status"],
    queryFn: api.system.status,
    refetchInterval: 10000,
    retry: 1,
  });

  let currentSection = "";

  return (
    <aside className="flex h-screen w-56 flex-col border-r bg-card">
      <div className="border-b p-4">
        <h1 className="text-lg font-bold">親亡き後支援DB</h1>
      </div>
      <nav className="flex-1 overflow-y-auto p-2">
        {NAV_ITEMS.map((item) => {
          const showSection = item.section !== currentSection;
          if (showSection) currentSection = item.section;
          return (
            <div key={item.href}>
              {showSection && (
                <p className="mt-4 mb-1 px-3 text-xs font-medium text-muted-foreground uppercase">
                  {item.section}
                </p>
              )}
              <Link
                href={item.href}
                className={`block rounded-md px-3 py-2 text-sm ${
                  pathname === item.href
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-muted"
                }`}
              >
                {item.label}
              </Link>
            </div>
          );
        })}
      </nav>
      <div className="border-t p-3 text-xs text-muted-foreground space-y-1">
        {isError ? (
          <div>API: 未接続 ○</div>
        ) : (
          <>
            <div>Chat: {status?.chat_provider === "claude" ? "Claude" : "Gemini"} {(status?.chat_provider === "claude" ? status?.claude_available : status?.gemini_available) ? "●" : "○"}</div>
            <div>Neo4j: {status?.neo4j_available ? "●" : "○"}</div>
          </>
        )}
      </div>
    </aside>
  );
}
