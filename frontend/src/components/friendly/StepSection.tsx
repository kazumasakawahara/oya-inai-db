"use client";
import { ReactNode } from "react";
import { Check } from "lucide-react";

export type StepState = "done" | "active" | "waiting";

interface Props {
  step: number;
  title: string;
  state: StepState;
  /** 「（任意）」表示を付ける */
  optional?: boolean;
  children: ReactNode;
}

/**
 * 番号丸付きのステップ枠。
 * done=✓緑 / active=強調 / waiting=淡色 で「次にやること」を1つだけ目立たせる。
 */
export function StepSection({ step, title, state, optional, children }: Props) {
  return (
    <section
      className={`rounded-lg border-2 p-4 transition-colors ${
        state === "active"
          ? "border-primary bg-background"
          : state === "done"
            ? "border-green-500 bg-green-50/50 dark:bg-green-950/20"
            : "border-border bg-muted/30 opacity-70"
      }`}
    >
      <div className="flex items-center gap-3 mb-3">
        <div
          className={`w-9 h-9 rounded-full flex items-center justify-center text-lg font-bold shrink-0 ${
            state === "done"
              ? "bg-green-600 text-white"
              : state === "active"
                ? "bg-primary text-primary-foreground"
                : "bg-muted-foreground/20 text-muted-foreground"
          }`}
        >
          {state === "done" ? <Check className="w-5 h-5" /> : step}
        </div>
        <h3 className="text-base font-bold">
          {title}
          {optional && (
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              （任意・あとで書けます）
            </span>
          )}
        </h3>
      </div>
      <div className="pl-12">{children}</div>
    </section>
  );
}
