"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { EcomapNode } from "@/lib/types";

interface Props {
  node: EcomapNode;
  onClose: () => void;
}

export function NodeDetailPanel({ node, onClose }: Props) {
  return (
    <div className="absolute top-0 right-0 w-80 h-full bg-[#333] border-l border-[#555] p-4 overflow-y-auto shadow-lg z-10">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div
            className="w-4 h-4 rounded-full"
            style={{ backgroundColor: node.color }}
          />
          <span className="text-white font-medium">{node.node_label}</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          className="text-gray-400 hover:text-white"
        >
          ✕
        </Button>
      </div>
      <h3 className="text-lg text-white font-bold mb-3">{node.label}</h3>
      {node.category === "ngActions" && node.properties.riskLevel != null && (
        <Badge variant="destructive" className="mb-3">
          {String(node.properties.riskLevel)}
        </Badge>
      )}
      <div className="space-y-2">
        {Object.entries(node.properties).map(([key, value]) => (
          <div key={key} className="border-b border-[#444] pb-2">
            <span className="text-xs text-gray-400">{key}</span>
            <p className="text-sm text-gray-200">{String(value)}</p>
          </div>
        ))}
        {Object.keys(node.properties).length === 0 && (
          <p className="text-sm text-gray-500">プロパティなし</p>
        )}
      </div>
    </div>
  );
}
