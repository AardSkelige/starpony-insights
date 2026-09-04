import type { HomeMonth } from "@/sections/home/api"
import { formatMoney } from "@/shared/lib/format"
import { cn } from "@/shared/lib/utils"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"

const MONTHS = [
  "янв", "фев", "мар", "апр", "май", "июн",
  "июл", "авг", "сен", "окт", "ноя", "дек",
]

/**
 * Выручка отгрузок по месяцам — растём или падаем.
 *
 * **Ось от нуля.** Столбики читают площадью, и обрезанная ось врёт о разнице
 * тем сильнее, чем ближе значения друг к другу (`DESIGN.md` §1). У линии
 * правило обратное, но линии здесь нет: вопрос «сколько в каждом месяце»,
 * а не «на сколько изменилось».
 *
 * **Один ряд рисуется `primary`, а не слотом палитры.** Различать нечего,
 * заголовок ряд и называет; слот `--chart-*` отвечает на «какая из серий»,
 * и взять его для единственной значило бы объявить столбикам разную природу.
 *
 * **Столбики блоками, а не SVG.** `preserveAspectRatio="none"` растягивает
 * вместе с рисунком и подписи — грабли `DESIGN.md` §15, пойманные на макете:
 * названия месяцев расползались по горизонтали.
 */
export function Months({ months }: { months: HomeMonth[] }) {
  const max = Math.max(...months.map((month) => month.revenue_kopecks), 0)
  if (max <= 0) return null

  return (
    <div className="flex h-24 items-end gap-1.5" role="img" aria-label="Выручка отгрузок по месяцам">
      {months.map((month) => (
        <Tooltip key={month.start}>
          <TooltipTrigger
            render={
              <div className="flex h-full min-w-0 flex-1 flex-col">
                <div className="flex flex-1 items-end border-b">
                  <div
                    className={cn(
                      "motion-bar-reveal w-full rounded-t-[3px] bg-primary",
                      // Идущий месяц бледный: он неполон и в сравнения
                      // не входит. Выкинуть его значило бы показать, что
                      // месяца не было вовсе, а поставить наравне —
                      // объявить падение на 90 % четвёртого числа.
                      month.partial && "opacity-35"
                    )}
                    style={{
                      // Минимум в две точки: месяц с продажами на 500 ₽ рядом
                      // с миллионным даёт долю в 0,05 % — столбик исчезает,
                      // и месяц читается как пустой.
                      height: `max(2px, ${(month.revenue_kopecks / max) * 100}%)`,
                    }}
                  />
                </div>
                <div className="pt-1 text-center text-[10px] text-muted-foreground">
                  {MONTHS[Number(month.start.slice(5, 7)) - 1]}
                </div>
              </div>
            }
          />
          <TooltipContent>
            {formatMoney(month.revenue_kopecks)}
            {month.partial ? " · месяц идёт" : ""}
          </TooltipContent>
        </Tooltip>
      ))}
    </div>
  )
}
