import type { Profitability } from "@/sections/profitability/api"
import { Split } from "@/sections/profitability/ui/split"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { formatMoney, formatShare } from "@/shared/lib/format"
import { cn } from "@/shared/lib/utils"

/**
 * «Итог за период»: три числа и состав выручки.
 *
 * Под таблицей и свёрнут, как на пяти соседних страницах: главное здесь —
 * сравнение товаров, а одно число за ними приходят реже. **Заголовок при
 * этом несёт прибыль и маржу** — свёрнутый блок обязан оставаться
 * осмысленным (`DESIGN.md` §7).
 *
 * Третья плитка — не число, а предупреждение в форме числа: сколько выручки
 * прошло через площадки, то есть по какой части маржа завышена.
 */
export function Summary({
  totals,
  coverage,
  marketplaces,
}: {
  totals: Profitability["totals"]
  coverage: Profitability["coverage"]
  marketplaces: Profitability["marketplaces"]
}) {
  const share =
    totals.revenue_kopecks > 0
      ? marketplaces.marketplace_revenue_kopecks / totals.revenue_kopecks
      : null

  return (
    <CollapsibleNote
      title="Итог за период"
      headline={`${formatMoney(totals.profit_kopecks)} · маржа ${formatShare(totals.margin)}`}
    >
      <div className="flex flex-col gap-5">
        <div className="grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-3">
          <Tile
            label="Прибыль за период"
            value={formatMoney(totals.profit_kopecks)}
            hint={`${formatMoney(totals.revenue_kopecks)} выручки − ${formatMoney(totals.cost_kopecks)} себестоимости`}
          />
          <Tile
            label="Маржа"
            value={formatShare(totals.margin)}
            hint={
              coverage.with_free
                ? "С подарками. Без них маржа выше"
                : "Без подарков. С ними она ниже"
            }
          />
          {marketplaces.marketplace_revenue_kopecks > 0 ? (
            <Tile
              label="Под вопросом — площадки"
              value={formatMoney(marketplaces.marketplace_revenue_kopecks)}
              hint={`${share === null ? "" : `${formatShare(String(share))} выручки. `}Комиссия Озона, Яндекса и ПМТ в учёт не заводится, и маржа по ним завышена`}
              tone="warning"
            />
          ) : null}
        </div>

        {/* Состав выручки одной полосой: отношение себестоимости к прибыли
            читается длиной, а не делением семизначных чисел в уме.

            При убытке полосы нет вовсе. Обрезанная до нуля прибыль
            превращала бы её в сплошную «себестоимость 100 %» под подписью
            «из чего сложилась выручка» — и убыток становился невидим
            ровно тогда, когда его и надо увидеть. */}
        {totals.profit_kopecks >= 0 ? (
          <Split
            left={{
              label: `${formatMoney(totals.cost_kopecks)} · себестоимость`,
              value: totals.cost_kopecks,
            }}
            right={{
              label: `${formatMoney(totals.profit_kopecks)} · прибыль`,
              value: totals.profit_kopecks,
            }}
            caption={`Из чего сложилась выручка ${formatMoney(totals.revenue_kopecks)}`}
          />
        ) : (
          <p className="text-sm text-destructive">
            Себестоимость проданного больше выручки на{" "}
            <b>{formatMoney(-totals.profit_kopecks)}</b> — за период сработали
            в убыток.
          </p>
        )}
      </div>
    </CollapsibleNote>
  )
}

function Tile({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: string
  hint: string
  tone?: "warning"
}) {
  return (
    <div className="bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-1 text-2xl font-semibold tracking-tight tabular-nums",
          tone === "warning" && "text-warning"
        )}
      >
        {value}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
    </div>
  )
}
