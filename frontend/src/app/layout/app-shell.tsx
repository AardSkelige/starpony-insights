import * as React from "react"
import { Outlet } from "react-router"

import { AppHeader } from "@/app/layout/app-header"
import { AppSidebar } from "@/app/layout/app-sidebar"
import {
  SIDEBAR_MAX_WIDTH,
  SIDEBAR_MIN_WIDTH,
} from "@/app/layout/sidebar-controls"
import type { Profile } from "@/shared/api/client"
import { SidebarInset, SidebarProvider } from "@/shared/ui/sidebar"

const WIDTH_KEY = "sidebar-width"
const DEFAULT_WIDTH = 256

function readWidth(): number {
  const stored = Number(localStorage.getItem(WIDTH_KEY))
  if (!Number.isFinite(stored) || stored <= 0) {
    return DEFAULT_WIDTH
  }
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, stored))
}

export function AppShell({ profile }: { profile: Profile }) {
  // Ширина живёт в браузере. Правильнее хранить её за пользователем в базе,
  // чтобы переживала смену браузера, — это появится вместе с моделью настроек,
  // там же, где закрепы «Избранного».
  const [width, setWidth] = React.useState(readWidth)

  // Во время перетаскивания меняется только то, что на экране.
  const showWidth = React.useCallback((next: number) => {
    setWidth(next)
  }, [])

  const saveWidth = React.useCallback((next: number) => {
    setWidth(next)
    localStorage.setItem(WIDTH_KEY, String(next))
  }, [])

  const resetWidth = React.useCallback(() => {
    saveWidth(DEFAULT_WIDTH)
  }, [saveWidth])

  return (
    <SidebarProvider style={{ "--sidebar-width": `${width}px` } as React.CSSProperties}>
      <AppSidebar
        profile={profile}
        onResize={showWidth}
        onCommitWidth={saveWidth}
        onResetWidth={resetWidth}
      />
      <SidebarInset>
        <AppHeader profile={profile} />
        <div className="flex flex-1 flex-col gap-4 p-4">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
