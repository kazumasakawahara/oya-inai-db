"use client";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

export function RecentActivity() {
  const { data, isError } = useQuery({ queryKey: ["dashboard-activity"], queryFn: api.dashboard.activity, retry: 1 });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">最近の活動</CardTitle></CardHeader>
      <CardContent>
        {isError ? <p className="text-sm text-destructive">活動履歴の取得に失敗しました</p> :
        !data?.length ? <p className="text-sm text-muted-foreground">活動なし</p> : (
          <ul className="space-y-2">
            {data.map((a, i) => (
              <li key={i} className="text-sm">
                <span className="text-muted-foreground">{a.date?.slice(0, 10)}</span>{" "}
                <span className="font-medium">{a.client_name}</span> {a.summary}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
