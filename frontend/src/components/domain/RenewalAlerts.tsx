"use client";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

export function RenewalAlerts() {
  const { data, isError } = useQuery({ queryKey: ["dashboard-alerts"], queryFn: api.dashboard.alerts, retry: 1 });
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">更新期限アラート</CardTitle></CardHeader>
      <CardContent>
        {isError ? <p className="text-sm text-destructive">アラートの取得に失敗しました</p> :
        !data?.length ? <p className="text-sm text-muted-foreground">アラートなし</p> : (
          <ul className="space-y-2">
            {data.map((a, i) => (
              <li key={i} className="flex items-center justify-between text-sm">
                <span>{a.client_name} — {a.certificate_type}</span>
                <Badge variant={a.days_remaining < 30 ? "destructive" : "secondary"}>
                  残{a.days_remaining}日
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
