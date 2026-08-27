import * as React from "react"
import { PanelLeft } from "lucide-react"

import { Button } from "@/shared/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"
import { useSidebar } from "@/shared/ui/sidebar"
import { cn } from "@/shared/lib/utils"

/**
 * Кнопка сворачивания и полоса для растягивания — свои, а не из реестра.
 *
 * Причина одна и та же: у `SidebarTrigger` и `SidebarRail` подписи зашиты
 * по-английски, причём у рельсы — через нативный `title`, который `DESIGN.md`
 * §3.1 запрещает: он выглядит по-разному в браузерах, появляется с задержкой
 * и не следует теме. Править файлы реестра нельзя — их обновляет CLI.
 */
export function SidebarToggle() {
  const { toggleSidebar } = useSidebar()

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Свернуть или развернуть сайдбар"
            onClick={toggleSidebar}
          >
            <PanelLeft />
          </Button>
        }
      />
      <TooltipContent>Свернуть сайдбар&nbsp;&nbsp;⌘B</TooltipContent>
    </Tooltip>
  )
}

export const SIDEBAR_MIN_WIDTH = 208
export const SIDEBAR_MAX_WIDTH = 400

/**
 * Полоса на правом краю сайдбара: тянет ширину, по двойному щелчку сворачивает.
 */
export function SidebarResizer({
  onResize,
  onCommit,
  onReset,
}: {
  /** Идёт перетаскивание: ширина меняется на экране. */
  onResize: (width: number) => void
  /** Перетаскивание закончено: ширину можно запоминать. */
  onCommit: (width: number) => void
  onReset: () => void
}) {
  const { toggleSidebar, state } = useSidebar()
  const [dragging, setDragging] = React.useState(false)

  const startDrag = React.useCallback(
    (event: React.PointerEvent<HTMLButtonElement>) => {
      // В свёрнутом виде тянуть нечего: ширина там фиксирована под иконки.
      if (state === "collapsed") {
        toggleSidebar()
        return
      }

      event.preventDefault()
      setDragging(true)

      // Ширина считается от левого края сайдбара, а не от края окна:
      // так она верна и когда сайдбар смещён относительно окна.
      const left = event.currentTarget.closest("[data-slot='sidebar']")
        ?.getBoundingClientRect().left ?? 0

      let width = SIDEBAR_MIN_WIDTH

      const move = (moveEvent: PointerEvent) => {
        width = Math.min(
          SIDEBAR_MAX_WIDTH,
          Math.max(SIDEBAR_MIN_WIDTH, moveEvent.clientX - left),
        )
        onResize(width)
      }

      const finish = () => {
        setDragging(false)
        // В хранилище пишем один раз, в конце. Синхронная запись на каждое
        // движение указателя — десятки обращений к диску за одно перетаскивание.
        onCommit(width)
        window.removeEventListener("pointermove", move)
        window.removeEventListener("pointerup", finish)
        // Курсор менялся на всё время перетаскивания: без этого он мигает,
        // когда указатель уходит за пределы узкой полосы.
        document.body.style.removeProperty("cursor")
        document.body.style.removeProperty("user-select")
      }

      document.body.style.cursor = "col-resize"
      document.body.style.userSelect = "none"
      window.addEventListener("pointermove", move)
      window.addEventListener("pointerup", finish)
    },
    [onCommit, onResize, state, toggleSidebar],
  )

  return (
    <button
      type="button"
      aria-label="Изменить ширину сайдбара"
      tabIndex={-1}
      onPointerDown={startDrag}
      onDoubleClick={onReset}
      className={cn(
        "absolute inset-y-0 -right-1 z-20 hidden w-2 md:block",
        // Подсвечивается сама граница сайдбара, а не рисуется вторая линия
        // рядом с ней: иначе при наведении их видно две.
        "after:absolute after:inset-y-0 after:right-1 after:w-px after:transition-colors",
        "hover:after:bg-sidebar-accent-foreground/40",
        dragging && "after:bg-sidebar-accent-foreground/40",
        // В свёрнутом виде тянуть нечего: ширина там фиксирована под иконки.
        // Полоса остаётся, но работает как «развернуть».
        "cursor-col-resize group-data-[collapsible=icon]:cursor-e-resize",
      )}
    />
  )
}
