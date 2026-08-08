"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60 * 1000,       // 5分間はキャッシュを新鮮とみなす
            gcTime: 10 * 60 * 1000,          // 10分間キャッシュを保持
            retry: 1,                        // リトライは1回まで
            refetchOnWindowFocus: false,      // タブ切り替え時の自動再取得を無効化
          },
        },
      }),
  );
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
