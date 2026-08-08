"use client";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

export function StatsCards() {
  const { data, isError } = useQuery({ queryKey: ["dashboard-stats"], queryFn: api.dashboard.stats, retry: 1 });

  if (isError) {
    return <p className="text-sm text-destructive">統計情報の取得に失敗しました</p>;
  }

  const stats = [
    { title: "利用者数", value: data?.client_count ?? "-" },
    { title: "今月の記録", value: data?.log_count_this_month ?? "-" },
    { title: "更新期限", value: data?.renewal_alerts ?? "-" },
  ];
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {stats.map((s) => (
        <Card key={s.title}>
          <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">{s.title}</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-bold">{s.value}</p></CardContent>
        </Card>
      ))}
    </div>
  );
}
