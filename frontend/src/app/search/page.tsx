"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchResults } from "@/components/domain/SearchResults";
import { api } from "@/lib/api";
import type { SemanticSearchResult } from "@/lib/types";

const INDEX_OPTIONS = [
  { value: "support_log_vector_index", label: "支援記録" },
  { value: "care_preference_embedding", label: "ケア指示" },
  { value: "ng_action_embedding", label: "禁忌事項" },
  { value: "client_summary_embedding", label: "クライアント概要" },
];

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [indexName, setIndexName] = useState("support_log_vector_index");
  const [results, setResults] = useState<SemanticSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(false);
    try {
      const data = await api.search.semantic(query, indexName);
      setResults(data);
      setSearched(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">セマンティック検索</h2>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">検索条件</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.nativeEvent.isComposing) handleSearch();
            }}
            placeholder="検索クエリを入力（例: パニック時の対応）"
          />
          <div className="flex gap-2 flex-wrap">
            {INDEX_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setIndexName(opt.value)}
                className={`px-3 py-1 rounded text-sm ${
                  indexName === opt.value
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-muted/80"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <Button onClick={handleSearch} disabled={!query.trim() || loading}>
            {loading ? "検索中..." : "検索"}
          </Button>
        </CardContent>
      </Card>
      {searched && (
        <div>
          <h3 className="text-lg font-medium mb-3">
            検索結果（{results.length}件）
          </h3>
          <SearchResults results={results} />
        </div>
      )}
    </div>
  );
}
