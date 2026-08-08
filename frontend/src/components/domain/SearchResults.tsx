"use client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { SemanticSearchResult } from "@/lib/types";

interface Props {
  results: SemanticSearchResult[];
}

// プロパティの日本語ラベル
const PROP_LABELS: Record<string, string> = {
  date: "日付",
  situation: "状況",
  action: "対応",
  effectiveness: "有効性",
  note: "メモ",
  name: "名前",
  category: "カテゴリ",
  instruction: "指示内容",
  priority: "優先度",
  riskLevel: "リスクレベル",
  reason: "理由",
  phone: "電話番号",
  relationship: "関係",
  address: "住所",
  type: "種類",
  dob: "生年月日",
  bloodType: "血液型",
};

// 非表示にするプロパティ
const HIDDEN_PROPS = new Set(["id", "embedding", "summaryEmbedding", "textEmbedding"]);

// 有効性の日本語表示
const EFFECTIVENESS: Record<string, string> = {
  "1": "効果的",
  "2": "やや効果的",
  "3": "どちらでもない",
  "4": "効果なし",
  Effective: "効果的",
  Ineffective: "効果なし",
  Neutral: "どちらでもない",
  Unknown: "不明",
};

function formatValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "-";
  const str = String(value);
  if (key === "effectiveness" && str in EFFECTIVENESS) return EFFECTIVENESS[str];
  // ISO日時を短縮表示
  if (key === "date" && str.includes("T")) return str.split("T")[0];
  return str;
}

export function SearchResults({ results }: Props) {
  if (!results.length)
    return <p className="text-sm text-muted-foreground">結果なし</p>;

  return (
    <div className="space-y-3">
      {results.map((r, i) => {
        const props = Object.entries(r.properties).filter(
          ([k]) => !HIDDEN_PROPS.has(k) && r.properties[k] !== null
        );

        // メインの表示テキストを決定
        const mainText =
          (r.properties.note as string) ||
          (r.properties.instruction as string) ||
          (r.properties.action as string) ||
          (r.properties.name as string) ||
          "";

        return (
          <Card key={i}>
            <CardContent className="pt-4">
              <div className="flex items-center justify-between mb-2">
                <Badge variant="outline">{r.node_label}</Badge>
                <span className="text-xs text-muted-foreground">
                  類似度: {(r.score * 100).toFixed(1)}%
                </span>
              </div>

              {/* メインテキスト */}
              {mainText && (
                <p className="text-sm mb-3">{mainText}</p>
              )}

              {/* プロパティ一覧 */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                {props.map(([key, value]) => {
                  // メインテキストとして既に表示したものはスキップ
                  if (
                    (key === "note" || key === "instruction" || key === "action" || key === "name") &&
                    String(value) === mainText
                  )
                    return null;

                  return (
                    <div key={key} className="flex justify-between">
                      <span className="text-muted-foreground">
                        {PROP_LABELS[key] || key}
                      </span>
                      <span className="text-right">
                        {formatValue(key, value)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
