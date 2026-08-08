"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  type Node as ReactFlowNode,
  type Edge as ReactFlowEdge,
  type NodeProps,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { EcomapData, EcomapNode as EcomapNodeType } from "@/lib/types";
import { NodeDetailPanel } from "./NodeDetailPanel";

// 中心に透明ハンドルを1つ配置 → エッジがノード中心から放射状に出る
const handleStyle = {
  opacity: 0,
  width: 1,
  height: 1,
  top: "50%",
  left: "50%",
  transform: "translate(-50%, -50%)",
  border: "none",
  background: "transparent",
} as const;

function CircleNode({ data }: NodeProps) {
  const size = data.isClient ? 80 : 55;
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        backgroundColor: data.color as string,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        cursor: "grab",
        border: `3px solid ${data.color as string}`,
        boxShadow: `0 0 10px ${data.color as string}40`,
        transition: "box-shadow 0.2s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = `0 0 20px ${data.color as string}80`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = `0 0 10px ${data.color as string}40`;
      }}
    >
      <span
        style={{
          color: "white",
          fontSize: data.isClient ? 13 : 10,
          fontWeight: 600,
          textAlign: "center",
          lineHeight: 1.2,
          padding: "2px 4px",
          overflow: "hidden",
          maxWidth: size - 10,
          wordBreak: "break-all",
        }}
      >
        {data.label as string}
      </span>
      <Handle type="source" position={Position.Top} id="center-src" style={handleStyle} />
      <Handle type="target" position={Position.Top} id="center-tgt" style={handleStyle} />
    </div>
  );
}

const nodeTypes = { circleNode: CircleNode };

function buildNodes(nodes: EcomapNodeType[]): ReactFlowNode[] {
  const centerX = 400;
  const centerY = 300;
  const clientNode = nodes.find((n) => n.category === "client");
  const otherNodes = nodes.filter((n) => n.category !== "client");

  const result: ReactFlowNode[] = [];

  if (clientNode) {
    result.push({
      id: clientNode.id,
      type: "circleNode",
      position: { x: centerX, y: centerY },
      data: { ...clientNode, isClient: true },
      draggable: true,
    });
  }

  const radius = Math.max(200, otherNodes.length * 20);
  otherNodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / otherNodes.length - Math.PI / 2;
    result.push({
      id: node.id,
      type: "circleNode",
      position: {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      },
      data: { ...node, isClient: false },
      draggable: true,
    });
  });

  return result;
}

function buildEdges(edges: EcomapData["edges"]): ReactFlowEdge[] {
  return edges.map((e, i) => ({
    id: `edge-${i}`,
    source: e.source,
    target: e.target,
    sourceHandle: "center-src",
    targetHandle: "center-tgt",
    label: e.label,
    type: "straight",
    style: { stroke: "#888", strokeWidth: 1.2 },
    labelStyle: { fill: "#aaa", fontSize: 9 },
    labelBgStyle: { fill: "#333", fillOpacity: 0.8 },
    labelBgPadding: [4, 2] as [number, number],
    labelBgBorderRadius: 3,
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: "#888",
      width: 12,
      height: 12,
    },
  }));
}

interface Props {
  data: EcomapData;
}

export function EcomapViewer({ data }: Props) {
  const [selectedNode, setSelectedNode] = useState<EcomapNodeType | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState(buildNodes(data.nodes));
  const [edges, setEdges, onEdgesChange] = useEdgesState(buildEdges(data.edges));

  // データが変わったらノードとエッジを再構築
  useEffect(() => {
    setNodes(buildNodes(data.nodes));
    setEdges(buildEdges(data.edges));
  }, [data, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: ReactFlowNode) => {
      const original = data.nodes.find((n) => n.id === node.id);
      if (original) setSelectedNode(original);
    },
    [data.nodes]
  );

  return (
    <div
      className="relative"
      style={{
        height: "calc(100vh - 220px)",
        background: "#2a2a2a",
        borderRadius: 8,
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodesDraggable={true}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        style={{ background: "#2a2a2a" }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#3a3a3a"
        />
        <Controls
          position="bottom-left"
          style={{ background: "#333", borderColor: "#555" }}
        />
        <MiniMap
          nodeColor={(n) => (n.data?.color as string) || "#888"}
          style={{ background: "#333", borderColor: "#555" }}
          maskColor="#2a2a2a80"
        />
      </ReactFlow>
      {selectedNode && (
        <NodeDetailPanel
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}
