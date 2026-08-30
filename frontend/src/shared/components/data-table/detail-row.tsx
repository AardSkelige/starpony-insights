import * as React from "react"

import { TableCell, TableRow } from "@/shared/ui/table"

/**
 * Строка с разбором, разворачивающаяся по высоте.
 *
 * **В таблице живёт только раскрытая строка и та, что сейчас схлопывается.**
 * Держать её у каждой строки заманчиво — тогда компонент переживает закрытие
 * сам, без помощи родителя, — но это удваивает число `tr` в таблице и вешает
 * `ResizeObserver` на каждую: при сотне строк на странице сто наблюдателей
 * там, где раскрыта всегда одна. Поэтому монтированием управляет `TableView`,
 * а отсюда наверх уходит только сигнал «схлопнулась, можно убирать».
 *
 * Высота измеряется заново через `ResizeObserver`: скелетон меняется на
 * асинхронные блоки уже после раскрытия, и фиксированная конечная высота
 * либо обрезала бы их, либо дёрнула таблицу вторым скачком.
 */
export function DetailRow({
  open,
  colSpan,
  onCollapsed,
  children,
}: {
  open: boolean
  colSpan: number
  /** Схлопывание закончилось — родителю пора размонтировать строку. */
  onCollapsed: () => void
  children: React.ReactNode
}) {
  const [height, setHeight] = React.useState(0)
  const contentRef = React.useRef<HTMLDivElement>(null)
  const reduceMotion =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches

  React.useLayoutEffect(() => {
    const content = contentRef.current
    if (!content) return

    const measure = () => setHeight(content.scrollHeight)
    const frame = requestAnimationFrame(measure)
    const observer =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure)
    observer?.observe(content)
    return () => {
      cancelAnimationFrame(frame)
      observer?.disconnect()
    }
  }, [open])

  // Без перехода некому сообщить о конце схлопывания: `transitionend`
  // не наступит вовсе, и строка осталась бы в таблице навсегда.
  React.useEffect(() => {
    if (!open && reduceMotion) onCollapsed()
  }, [open, reduceMotion, onCollapsed])

  return (
    <TableRow className="hover:bg-transparent" aria-hidden={!open}>
      {/* `whitespace-normal` обязателен: `TableCell` из реестра объявляет
          `whitespace-nowrap`, и разбор строки это наследует — абзацы внутри
          идут одной строкой и уползают за край экрана. */}
      <TableCell colSpan={colSpan} className="p-0 whitespace-normal">
        <div
          className="motion-panel-height overflow-hidden"
          // При отключённом движении не ждём даже кадр измерения: содержимое
          // появляется сразу в естественной высоте.
          style={{ height: open ? (reduceMotion ? "auto" : height) : 0 }}
          onTransitionEnd={(event) => {
            if (
              event.target === event.currentTarget &&
              event.propertyName === "height" &&
              !open
            ) {
              onCollapsed()
            }
          }}
        >
          <div ref={contentRef} className="bg-accent/40">
            {children}
          </div>
        </div>
      </TableCell>
    </TableRow>
  )
}
