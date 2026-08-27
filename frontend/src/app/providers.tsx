import * as React from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import { ThemeProvider } from "@/app/theme-provider"
import { ApiError } from "@/shared/api/client"
import { TooltipProvider } from "@/shared/ui/tooltip"

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Повторять запрос, на который сервер ответил «не вошёл» или «нет прав»,
        // бессмысленно: ответ не изменится, а человек ждёт лишние секунды.
        retry: (failureCount, error) => {
          if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
            return false
          }
          return failureCount < 2
        },
        staleTime: 30_000,
      },
    },
  })
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(makeQueryClient)

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        {/* Адаптер nuqs переехал внутрь роутера: ему нужен контекст
            маршрутизации, которого здесь ещё нет. */}
        <TooltipProvider>{children}</TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
