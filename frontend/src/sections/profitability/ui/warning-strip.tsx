import { TriangleAlert } from "lucide-react"

import type { Profitability } from "@/sections/profitability/api"
import { formatMoney, formatShare } from "@/shared/lib/format"

/**
 * Оговорка про комиссию площадок — между фильтрами и таблицей.
 *
 * **Выше чисел, а не рядом с ними.** Главная опасность этой страницы —
 * принять маржу Озона в 90,5 % за факт: комиссию площадка удерживает
 * при выплате, отдельного документа с ней в учёте нет, и вычесть её
 * неоткуда. Молча показать такое число нельзя (`PRD.md` §5.10).
 *
 * Полосой, а не подсказкой по наведению: подсказку открывают, уже приняв
 * решение по числу.
 *
 * Не показывается, когда площадок в выборке нет вовсе, — предупреждение
 * без повода перестают читать, и вместе с ним перестают читать все.
 */
export function WarningStrip({
  marketplaces,
  revenue,
}: {
  marketplaces: Profitability["marketplaces"]
  revenue: number
}) {
  if (marketplaces.marketplace_revenue_kopecks <= 0) return null

  const share =
    revenue > 0 ? marketplaces.marketplace_revenue_kopecks / revenue : null

  return (
    <div className="flex items-start gap-3 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm">
      <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
      <p className="min-w-0">
        <span className="font-medium">
          Комиссия площадок в марже не учтена — её нет в учёте.
        </span>{" "}
        <span className="text-muted-foreground">
          Через Озон, Яндекс.Маркет и ПМТ прошло{" "}
          {formatMoney(marketplaces.marketplace_revenue_kopecks)}
          {share === null ? null : (
            <> — {formatShare(String(share))} выручки</>
          )}
          . Их маржа {formatShare(marketplaces.marketplace_margin)} против{" "}
          {formatShare(marketplaces.direct_margin)} напрямую: разницу съедает
          комиссия, которую площадка удерживает при выплате.
        </span>
      </p>
    </div>
  )
}
