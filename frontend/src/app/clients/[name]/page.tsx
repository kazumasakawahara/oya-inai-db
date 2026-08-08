"use client";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";

export default function ClientDetailPage() {
  const params = useParams();
  const name = decodeURIComponent(params.name as string);
  const { data: client, isLoading, isError, error } = useQuery({
    queryKey: ["client", name],
    queryFn: () => api.clients.get(name),
    retry: 1,
  });

  if (isLoading) return <p className="text-muted-foreground">読み込み中...</p>;
  if (isError) return (
    <div className="space-y-2">
      <p className="text-destructive font-medium">クライアント情報の取得に失敗しました</p>
      <p className="text-sm text-muted-foreground">{error?.message ?? "不明なエラー"}</p>
    </div>
  );
  if (!client) return <p className="text-muted-foreground">データが見つかりません</p>;

  const riskColor = (level: string) => {
    if (level === "LifeThreatening") return "destructive";
    if (level === "Panic") return "secondary";
    return "outline";
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">{name}</h2>
      <Tabs defaultValue="basic">
        <TabsList>
          <TabsTrigger value="basic">基本情報</TabsTrigger>
          <TabsTrigger value="ng">禁忌事項</TabsTrigger>
          <TabsTrigger value="care">ケア指示</TabsTrigger>
          <TabsTrigger value="contacts">連絡先</TabsTrigger>
        </TabsList>

        <TabsContent value="basic">
          <Card>
            <CardContent className="pt-6 space-y-2">
              <p>生年月日: {(client as any).dob ?? "不明"}</p>
              <p>年齢: {(client as any).age ?? "不明"}</p>
              <p>血液型: {(client as any).blood_type ?? "不明"}</p>
              <div>
                <p className="font-medium mb-1">状態・障害:</p>
                <div className="flex gap-1 flex-wrap">
                  {((client as any).conditions ?? []).map((c: any, i: number) => (
                    <Badge key={i} variant="outline">{c.name ?? c}</Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ng">
          <Card>
            <CardContent className="pt-6">
              {((client as any).ng_actions ?? []).length === 0 ? (
                <p className="text-muted-foreground">禁忌事項なし</p>
              ) : (
                <ul className="space-y-3">
                  {((client as any).ng_actions ?? []).map((ng: any, i: number) => (
                    <li key={i} className="border rounded p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge variant={riskColor(ng.risk_level ?? ng.riskLevel) as any}>{ng.risk_level ?? ng.riskLevel}</Badge>
                        <span className="font-medium">{ng.action}</span>
                      </div>
                      {ng.reason && <p className="text-sm text-muted-foreground">{ng.reason}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="care">
          <Card>
            <CardContent className="pt-6">
              {((client as any).care_preferences ?? []).length === 0 ? (
                <p className="text-muted-foreground">ケア指示なし</p>
              ) : (
                <ul className="space-y-2">
                  {((client as any).care_preferences ?? []).map((cp: any, i: number) => (
                    <li key={i} className="border rounded p-3">
                      <span className="font-medium">{cp.category}:</span> {cp.instruction}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="contacts">
          <Card>
            <CardContent className="pt-6">
              {((client as any).key_persons ?? []).length === 0 ? (
                <p className="text-muted-foreground">連絡先なし</p>
              ) : (
                <ul className="space-y-2">
                  {((client as any).key_persons ?? []).map((kp: any, i: number) => (
                    <li key={i} className="border rounded p-3">
                      <span className="font-medium">{kp.name}</span>
                      {kp.relationship && <span className="text-muted-foreground"> ({kp.relationship})</span>}
                      {kp.phone && <span className="ml-2">{kp.phone}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
