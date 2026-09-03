import type { ProfitabilityRow } from "@/sections/profitability/api"
import { useProfitWidth } from "@/sections/profitability/ui/profit-scale"
import { formatMoney, formatShare } from "@/shared/lib/format"
import { cn } from "@/shared/lib/utils"

/**
 * Ячейки таблицы, которым нужен не только текст.
 *
 * Отдельным файлом от `columns.tsx`: там рядом живут `COLUMNS`, `SORT_KEYS`
 * и `totalsFor`, а компонент в одном файле с ними ломает горячую
 * перезагрузку — правило `react-refresh/only-export-components`.
 */

/**
 * Значок «часть ушла через площадку» — с долей выручки строки.
 *
 * **Число обязательно, и вот почему.** Без него значок стоял у десяти строк
 * из десяти: через площадки идёт почти весь ассортимент, и метка,
 * повторённая на каждой строке, перестаёт что-либо выделять — её работу
 * уже делает полоса предупреждения над таблицей. С долей она отвечает
 * на другой вопрос: **насколько** сомнительна маржа именно этой строки.
 * Разброс настоящий — от 4 % до 46 %.
 *
 * Подпись рядом с цветом обязательна: цвет кодирует не категорию,
 * а надёжность числа, и цветом в одиночку такое не говорят (`DESIGN.md` §1).
 */
export function MarketplaceMark({ share }: { share: number | null }) {
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-warning px-1.5 text-[11px] leading-[17px] text-warning"
      title="Столько выручки строки прошло через площадку. Её комиссия из прибыли не вычтена — в учёте её нет."
    >
      <span aria-hidden className="size-1 rounded-full bg-warning" />
      площадка{share === null ? "" : ` ${formatShare(String(share))}`}
    </span>
  )
}

/**
 * Прибыль с полосой под числом.
 *
 * Полоса меряется от наибольшей прибыли на странице, а не от итога: строки
 * сравниваются между собой, и шкала от итога сплющила бы их все в кромку —
 * у лидера всего 17,5 % общей прибыли. Масштаб приходит контекстом: он
 * зависит от соседей, о которых колонка не знает.
 */
export function ProfitCell({ row }: { row: ProfitabilityRow }) {
  const width = useProfitWidth(row.profit_kopecks)

  if (row.profit_kopecks === null) {
    // Прочерк, а не ноль: себестоимости в отчёте нет, и делить не на что.
    return <span className="text-muted-foreground">—</span>
  }

  const negative = row.profit_kopecks < 0

  return (
    <span className="flex flex-col items-end gap-1 max-sm:items-start">
      <span className={negative ? "text-destructive" : undefined}>
        {formatMoney(row.profit_kopecks)}
      </span>
      <span
        aria-hidden
        className="block h-[5px] w-full min-w-24 overflow-hidden rounded-[3px] bg-muted"
      >
        <span
          className={cn(
            "motion-bar-reveal block h-full rounded-[3px]",
            negative ? "bg-destructive" : "bg-primary"
          )}
          style={{ width }}
        />
      </span>
    </span>
  )
}
