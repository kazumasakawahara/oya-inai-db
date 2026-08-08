"use client";

import { useEffect, useRef } from "react";
import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { Sigma } from "sigma";
import { getNodeColor } from "@/lib/graphColors";

export type GraphData = {
  nodes: Array<{ id: string; label: string; name: string; properties: Record<string, unknown> }>;
  edges: Array<{ id: string; source: string; target: string; type: string; properties: Record<string, unknown> }>;
  truncated: boolean;
};

export type SelectedNode = {
  id: string;
  label: string;
  name: string;
  properties: Record<string, unknown>;
};

type Props = {
  data: GraphData;
  onNodeClick?: (node: SelectedNode) => void;
};

export function KnowledgeGraphViewer({ data, onNodeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const graph = new Graph();

    // Add nodes
    data.nodes.forEach((n) => {
      const degree = data.edges.filter((e) => e.source === n.id || e.target === n.id).length;
      graph.addNode(n.id, {
        label: n.name,
        size: Math.max(6, Math.min(20, 6 + degree * 1.5)),
        color: getNodeColor(n.label),
        nodeType: n.label,
        x: Math.random(),
        y: Math.random(),
      });
    });

    // Add edges
    data.edges.forEach((e) => {
      if (graph.hasNode(e.source) && graph.hasNode(e.target) && !graph.hasEdge(e.id)) {
        try {
          graph.addEdgeWithKey(e.id, e.source, e.target, {
            label: e.type,
            size: 1.5,
            color: "#94a3b8",
            type: "arrow",
          });
        } catch {
          // skip duplicate edges
        }
      }
    });

    // Run force-atlas2 layout
    if (graph.order > 1) {
      forceAtlas2.assign(graph, {
        iterations: 100,
        settings: {
          gravity: 1,
          scalingRatio: 10,
          slowDown: 2,
          barnesHutOptimize: graph.order > 100,
        },
      });
    }

    // Initialize sigma
    const sigma = new Sigma(graph, containerRef.current, {
      renderLabels: true,
      labelSize: 12,
      labelColor: { color: "#1f2937" },
      labelWeight: "500",
      defaultEdgeColor: "#cbd5e1",
      defaultNodeColor: "#64748b",
    });

    // Click handler
    sigma.on("clickNode", (e) => {
      const sourceNode = data.nodes.find((n) => n.id === e.node);
      if (sourceNode && onNodeClick) {
        onNodeClick(sourceNode);
      }
    });

    // Hover highlight
    sigma.on("enterNode", (e) => {
      const neighbors = new Set(graph.neighbors(e.node));
      neighbors.add(e.node);
      sigma.setSetting("nodeReducer", (nodeId, attrs) => {
        if (!neighbors.has(nodeId)) {
          return { ...attrs, color: "#e2e8f0", label: "" };
        }
        return attrs;
      });
      sigma.setSetting("edgeReducer", (edgeId, attrs) => {
        const [src, tgt] = graph.extremities(edgeId);
        if (!neighbors.has(src) || !neighbors.has(tgt)) {
          return { ...attrs, hidden: true };
        }
        return attrs;
      });
    });

    sigma.on("leaveNode", () => {
      sigma.setSetting("nodeReducer", null);
      sigma.setSetting("edgeReducer", null);
    });

    sigmaRef.current = sigma;

    return () => {
      sigma.kill();
      sigmaRef.current = null;
    };
  }, [data, onNodeClick]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full bg-white rounded-md border"
      style={{ minHeight: "600px" }}
    />
  );
}
