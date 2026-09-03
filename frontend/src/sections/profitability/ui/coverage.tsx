import type { Profitability } from "@/sections/profitability/api"
import { Split } from "@/sections/profitability/ui/split"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { formatMoney, formatQuantity } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * «Полнота расчёта»: что осталось за пределами маржи и почему.
 *
 * Отвечает на вопрос, который иначе задают вслух каждый раз: **почему здесь
 * меньше, чем в «Товарах в отгрузках»**. Разница — товар, ушедший
 * по договору комиссии: МойСклад считает его проданным только с приходом
 * отчёта комиссионера. Обе цифры верны, и разница обязана быть числом
 * на экране, а не расхождением между страницами.
 *
 * Поиск этот блок не сужает: он про полноту всей выборки, а не показанных
 * строк. Иначе «полное ли то, что показано» менялось бы от набранного
 * в поле слова.
 */
export function Coverage({
  coverage,
}: {
  coverage: Profitability["coverage"]
}) {
  const unsold = coverage.shipped_revenue_kopecks - coverage.sold_revenue_kopecks

  return (
    <CollapsibleNote
      title="Полнота расчёта"
      headline={headline(coverage, unsold)}
    >
      <div className="flex flex-col gap-5">
        {unsold > 0 ? (
          <Split
            left={{
              label: `Продано · ${formatMoney(coverage.sold_revenue_kopecks)}`,
              value: coverage.sold_revenue_kopecks,
            }}
            right={{
              label: `На реализации · ${formatMoney(unsold)}`,
              value: unsold,
            }}
            // Главное здесь — проданное: оно и есть выручка страницы.
            emphasis="left"
            caption={
              <>
                Со склада уехало на{" "}
                {formatMoney(coverage.shipped_revenue_kopecks)} — столько
                показывают «Товары в отгрузках». Деньги за товар приходят
                с отчётом комиссионера, и{" "}
                {formatQuantity(coverage.unsold_quantity)} шт пока лежат
                у него непроданными.
              </>
            }
          />
        ) : null}

        <dl className="flex flex-col gap-2 text-sm">
          <Fact
            term="Отдано даром — себестоимость есть, выручки нет"
            value={`${formatQuantity(coverage.free_quantity)} шт · ${formatMoney(coverage.free_cost_kopecks)}`}
          />
          {coverage.hidden_products_count > 0 ? (
            <Fact
              term="Скрыто строк: в этой базе у них ни штук, ни выручки"
              value={withPlural(
                coverage.hidden_products_count, "товар", "товара", "товаров"
              )}
            />
          ) : null}
          <Fact
            term="Что считается выручкой"
            value={
              coverage.basis === "sold"
                ? "деньги за товар"
                : "всё, что уехало со склада"
            }
          />
        </dl>
      </div>
    </CollapsibleNote>
  )
}

function headline(coverage: Profitability["coverage"], unsold: number): string {
  if (unsold > 0) {
    return `${formatMoney(unsold)} отгружено, но ещё не продано`
  }
  return `${formatQuantity(coverage.free_quantity)} шт отдано даром`
}

function Fact({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-muted-foreground">{term}</dt>
      <dd className="shrink-0 tabular-nums">{value}</dd>
    </div>
  )
}
