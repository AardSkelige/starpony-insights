import { ArrowDown, ArrowUp } from "lucide-react"

import type { HomeFigure } from "@/sections/home/api"
import { formatFigure } from "@/sections/home/format"
import { cn } from "@/shared/lib/utils"

/**
 * Число пульса вместе с тем, во что оно превратилось из прошлого месяца.
 *
 * **У маржи изменение считается пунктами, а не процентами.** Рост с 47,6 %
 * до 69,9 % — это +22,3 пункта; «+47 %» арифметически верно и читается
 * как ложь, потому что маржа не может вырасти вдвое, оставаясь в пределах
 * ста процентов. Сервер шлёт уже правильную величину, здесь остаётся
 * подписать её верной единицей.
 *
 * **Прошлое значение — на виду, а не в подсказке.** «+148 %» без основания
 * не проверяется, а проверять такие числа приходят первым делом.
 */
export function Figure({ figure }: { figure: HomeFigure }) {
  const change = figure.change === null ? null : Number(figure.change)
  const up = change !== null && change > 0
  const Arrow = up ? ArrowUp : ArrowDown

  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <div className="text-xl font-semibold tracking-tight tabular-nums">
        {formatFigure(figure.value, figure.unit)}
      </div>
      <div className="flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
        <span>{figure.label}</span>
        {change === null ? (
          // Прошлый месяц был нулевым: доли не существует, делить не на что.
          // «+∞ %» читалось бы как поломка, ноль — как «не изменилось».
          <span>· с нуля</span>
        ) : change === 0 ? (
          <span>· без изменений</span>
        ) : (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 font-medium tabular-nums",
              up ? "text-success" : "text-destructive"
            )}
          >
            {/* Стрелка рядом с цветом: направление не передаётся цветом
                в одиночку — правило `DESIGN.md` §1. */}
            <Arrow className="size-3" aria-hidden />
            {Math.abs(change).toFixed(1).replace(".", ",")}
            {figure.unit === "percent" ? " п.п." : " %"}
          </span>
        )}
      </div>
      <div className="text-xs text-muted-foreground tabular-nums">
        было {formatFigure(figure.earlier, figure.unit)}
      </div>
    </div>
  )
}
