"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SelectedNode } from "@/components/domain/KnowledgeGraphViewer";
import { NODE_COLORS, LABEL_JP, getNodeColor } from "@/lib/graphColors";
import { api } from "@/lib/api";

// Sigma.js uses WebGL and must not be pre-rendered on the server
const KnowledgeGraphViewer = dynamic(
  () =>
    import("@/components/domain/KnowledgeGraphViewer").then(
      (mod) => mod.KnowledgeGraphViewer
    ),
  { ssr: false }
);

export default function GraphPage() {
  const [startLabel, setStartLabel] = useState<string>("");
  const [startName, setStartName] = useState<string>("");
  const [maxDepth, setMaxDepth] = useState<number>(2);
  const [maxNodes, setMaxNodes] = useState<number>(100);
  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null);

  const { data: stats } = useQuery({
    queryKey: ["graph-stats"],
    queryFn: () => api.graph.stats(),
    retry: 1,
  });

  const { data: labels } = useQuery({
    queryKey: ["graph-labels"],
    queryFn: () => api.graph.labels(),
    retry: 1,
  });

  const {
    data: graphData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["graph-explore", startLabel, startName, maxDepth, maxNodes],
    queryFn: () =>
      api.graph.explore({
        startLabel: startLabel || undefined,
        startName: startName || undefined,
        maxDepth,
        maxNodes,
      }),
    retry: 1,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">知識グラフ</h2>
        {stats && (
          <div className="flex gap-4 text-sm text-muted-foreground">
            <span>総ノード: {stats.total_nodes.toLocaleString()}</span>
            <span>総関係: {stats.total_edges.toLocaleString()}</span>
          </div>
        )}
      </div>

      {/* Controls */}
      <Card>
        <CardContent className="pt-6 space-y-3">
          <div className="flex gap-3 flex-wrap items-end">
            <div>
              <label className="text-sm font-medium mb-1 block">起点ラベル</label>
              <select
                value={startLabel}
                onChange={(e) => {
                  setStartLabel(e.target.value);
                  setStartName("");
                }}
                className="border rounded px-3 py-2 text-sm min-w-[160px]"
              >
                <option value="">指定なし（概観）</option>
                {labels?.labels?.map((l) => (
                  <option key={l.label} value={l.label}>
                    {LABEL_JP[l.label] || l.label} ({l.count})
                  </option>
                ))}
              </select>
            </div>
            {startLabel && (
              <div>
                <label className="text-sm font-medium mb-1 block">ノード名</label>
                <input
                  type="text"
                  value={startName}
                  onChange={(e) => setStartName(e.target.value)}
                  placeholder="任意: 特定ノードから展開"
                  className="border rounded px-3 py-2 text-sm min-w-[200px]"
                />
              </div>
            )}
            <div>
              <label className="text-sm font-medium mb-1 block">深さ</label>
              <select
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value))}
                className="border rounded px-3 py-2 text-sm"
              >
                {[1, 2, 3, 4].map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium mb-1 block">最大ノード数</label>
              <select
                value={maxNodes}
                onChange={(e) => setMaxNodes(Number(e.target.value))}
                className="border rounded px-3 py-2 text-sm"
              >
                {[50, 100, 200, 300, 500].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
            <Button onClick={() => refetch()}>更新</Button>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-2 pt-2 border-t">
            {Object.entries(NODE_COLORS).slice(0, 12).map(([label, color]) => (
              <div key={label} className="flex items-center gap-1 text-xs">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                <span>{LABEL_JP[label] || label}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Graph + Detail Panel */}
      <div className="grid grid-cols-4 gap-4" style={{ height: "70vh" }}>
        <div className="col-span-3">
          <Card className="h-full">
            <CardContent className="pt-6 h-full">
              {isLoading && <div className="text-center py-8">読み込み中...</div>}
              {isError && <div className="text-center py-8 text-red-600">データ取得失敗</div>}
              {graphData && graphData.nodes.length === 0 && (
                <div className="text-center py-8 text-muted-foreground">
                  該当するデータがありません
                </div>
              )}
              {graphData && graphData.nodes.length > 0 && (
                <div className="h-full">
                  <KnowledgeGraphViewer
                    data={graphData}
                    onNodeClick={setSelectedNode}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        <div>
          <Card className="h-full overflow-auto">
            <CardContent className="pt-6">
              <h3 className="font-semibold mb-3">ノード詳細</h3>
              {selectedNode ? (
                <div className="space-y-3">
                  <div>
                    <Badge
                      style={{ backgroundColor: getNodeColor(selectedNode.label) }}
                      className="text-white"
                    >
                      {LABEL_JP[selectedNode.label] || selectedNode.label}
                    </Badge>
                  </div>
                  <div>
                    <h4 className="font-medium">{selectedNode.name}</h4>
                  </div>
                  <div className="space-y-1 text-sm">
                    {Object.entries(selectedNode.properties).map(([k, v]) => (
                      <div key={k} className="flex gap-2">
                        <span className="text-muted-foreground min-w-[80px]">{k}:</span>
                        <span className="break-all">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  ノードをクリックすると詳細が表示されます
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {graphData?.truncated && (
        <div className="text-sm text-amber-600">
          ⚠ 表示ノード数の上限に達しました。起点ラベルで絞り込むと詳細が見えます。
        </div>
      )}
    </div>
  );
}
