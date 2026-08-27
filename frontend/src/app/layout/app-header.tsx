import { Bell, Search } from "lucide-react"
import { useLocation } from "react-router"

import { ICON_GROUP } from "@/app/layout/icon-group"
import { SidebarToggle } from "@/app/layout/sidebar-controls"
import { ThemeSwitch } from "@/app/layout/theme-switch"
import type { Profile } from "@/shared/api/client"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/shared/ui/breadcrumb"
import { Button } from "@/shared/ui/button"
import { Separator } from "@/shared/ui/separator"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"

/**
 * Шапка узкая и почти пустая: место отдано содержимому.
 * Поля поиска здесь нет — только подсказка, открывающая палитру команд.
 */
export function AppHeader({ profile }: { profile: Profile }) {
  const { pathname } = useLocation()
  const current = profile.pages.find((page) => page.route === pathname)

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b px-3">
      <SidebarToggle />

      {/* Высота задаётся явно: сам компонент растягивается на всю высоту
          родителя, и без этого черта тянется от края до края шапки. */}
      <Separator
        orientation="vertical"
        className="mx-1 data-vertical:h-4 data-vertical:self-center"
      />

      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden sm:block">StarPony</BreadcrumbItem>
          {current ? (
            <>
              <BreadcrumbSeparator className="hidden sm:block" />
              <BreadcrumbItem>
                <BreadcrumbPage>{current.label}</BreadcrumbPage>
              </BreadcrumbItem>
            </>
          ) : null}
        </BreadcrumbList>
      </Breadcrumb>

      <div className="ml-auto flex items-center gap-2">
        <div className={ICON_GROUP}>
          <Tooltip>
            <TooltipTrigger
              render={
                <Button variant="ghost" size="icon-sm" aria-label="Поиск">
                  <Search />
                </Button>
              }
            />
            <TooltipContent>Поиск&nbsp;&nbsp;⌘K</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger
              render={
                <Button variant="ghost" size="icon-sm" aria-label="Уведомления">
                  <Bell />
                </Button>
              }
            />
            <TooltipContent>Уведомления</TooltipContent>
          </Tooltip>
        </div>

        <ThemeSwitch />
      </div>
    </header>
  )
}
