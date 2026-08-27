import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"

export type Bar = {
  key: string
  label: string
  /** Длина полосы. Доля считается от наибольшего значения в списке. */
  value: number
  /** Что показать у конца полосы. */
  display: string
  /** Что показать по наведению — второе измерение, не влезшее в подпись. */
  hint?: string
}

/**
 * Горизонтальные полосы: сравнение величин по категориям.
 *
 * **Все полосы одного цвета.** Категории здесь номинальные — каналы продаж
 * не упорядочены и не образуют шкалу, поэтому красить каждую своим цветом
 * значило бы второй раз закодировать то, что уже показывает длина, и сжечь
 * единственный свободный канал впустую. В утверждённом макете полосы были
 * разноцветными — это как раз тот случай.
 *
 * Цвет — `primary`, а не `chart-*`: в теме `nova` палитра графиков нейтральная
 * и одинаковая в светлой и тёмной теме, поэтому `chart-1` на белом фоне даёт
 * контраст 1.48, а `chart-5` на тёмном — 1.31, при пороге 3:1. У `primary`
 * проверка проходит в обеих темах.
 */
export function BarList({ bars }: { bars: Bar[] }) {
  const max = Math.max(...bars.map((bar) => bar.value), 0)
  if (max <= 0) return null

  return (
    <div className="flex flex-col gap-1.5">
      {bars.map((bar) => (
        <Tooltip key={bar.key}>
          <TooltipTrigger
            render={
              <div className="flex items-center gap-3 text-sm">
                <span className="w-24 shrink-0 truncate text-xs text-muted-foreground">
                  {bar.label}
                </span>
                {/* Дорожка во всю ширину: без неё полосы не с чем сравнивать,
                    кроме друг друга, и доля от целого не читается. */}
                <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-[3px] bg-muted">
                  <span
                    className="block h-full rounded-r-[3px] bg-primary"
                    style={{ width: `${(bar.value / max) * 100}%` }}
                  />
                </span>
                <span className="w-16 shrink-0 text-right text-xs tabular-nums">
                  {bar.display}
                </span>
              </div>
            }
          />
          {bar.hint ? <TooltipContent>{bar.hint}</TooltipContent> : null}
        </Tooltip>
      ))}
    </div>
  )
}
