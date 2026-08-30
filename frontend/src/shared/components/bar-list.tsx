import { cn } from "@/shared/lib/utils"
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
  /**
   * Второе число у конца полосы: доля, процент, разница.
   *
   * Приглушено и уже основного: полоса и `display` отвечают на «сколько»,
   * а это уточняет «какая часть» — читается вторым, а не наравне.
   */
  secondary?: string
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
export function BarList({
  bars,
  wideLabels = false,
}: {
  bars: Bar[]
  /**
   * Широкая колонка подписей.
   *
   * Не вкус, а разница в данных: названия каналов короткие («ХорсСмарт»,
   * «Точка продаж»), а имена получателей — нет («ГКФХ Торшин Валерий
   * Вячеславович»). Обрезанное имя перестаёт быть опознавательным знаком,
   * а полоса и без того длинная — отдать ей часть ширины дешевле, чем
   * потерять того, о ком строка.
   */
  wideLabels?: boolean
}) {
  const max = Math.max(...bars.map((bar) => bar.value), 0)
  if (max <= 0) return null

  return (
    <div className="flex flex-col gap-1.5">
      {bars.map((bar) => (
        <Tooltip key={bar.key}>
          <TooltipTrigger
            render={
              <div className="flex items-center gap-3 text-sm">
                <span
                  className={cn(
                    "shrink-0 truncate text-xs text-muted-foreground",
                    wideLabels ? "w-44" : "w-24"
                  )}
                >
                  {bar.label}
                </span>
                {/* Дорожка во всю ширину: без неё полосы не с чем сравнивать,
                    кроме друг друга, и доля от целого не читается. */}
                <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-[3px] bg-muted">
                  <span
                    className="motion-bar-reveal block h-full rounded-r-[3px] bg-primary"
                    style={{ width: `${(bar.value / max) * 100}%` }}
                  />
                </span>
                {/* Ширина под самое длинное, что сюда попадает, — денежную
                    сумму «23 350,00 ₽». Колонка чисел обязана выравниваться
                    по правому краю, поэтому ширина фиксированная: подгонка
                    по содержимому дала бы рваный столбец. */}
                <span className="w-24 shrink-0 text-right text-xs whitespace-nowrap tabular-nums">
                  {bar.display}
                </span>
                {bar.secondary ? (
                  <span className="w-12 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                    {bar.secondary}
                  </span>
                ) : null}
              </div>
            }
          />
          {bar.hint ? <TooltipContent>{bar.hint}</TooltipContent> : null}
        </Tooltip>
      ))}
    </div>
  )
}
