import { Check } from "lucide-react"

import type { Profitability, ProfitabilityRow } from "@/sections/profitability/api"
import { BarList, type Bar } from "@/shared/components/bar-list"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { formatMoney, formatQuantity, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/** Сколько строк подарков показывать. Больше — это уже таблица, а не ответ. */
const TOP = 5

/**
 * «Подарки и убытки» — один блок, а не два.
 *
 * Они об одном: пять позиций уходят в минус **только вместе с подарками**,
 * и четыре из пяти вообще не продавались — «Амуницию» отдавали исключительно
 * даром. Разведи их по разным блокам, и «продано в убыток» читалось бы
 * как ошибка в цене, которой нет.
 *
 * Здесь же видно, чего стоит щедрость: 86 610 ₽ себестоимости у 497 штук
 * без выручки — восемь с половиной пунктов маржи.
 */
export function FreeAndLosses({
  coverage,
  losses,
}: {
  coverage: Profitability["coverage"]
  losses: ProfitabilityRow[]
}) {
  if (Number(coverage.free_quantity) <= 0 && losses.length === 0) return null

  const generous = topFree(coverage.most_given_away)

  return (
    <CollapsibleNote
      title="Подарки и убытки"
      headline={headline(coverage, losses.length)}
    >
      <div className="flex flex-col gap-6">
        {Number(coverage.free_quantity) > 0 ? (
          <section className="flex flex-col gap-3">
            <h3 className="text-xs text-muted-foreground">
              Чего стоит отданное даром
            </h3>
            <p className="text-sm">
              {withPlural(
                Math.round(Number(coverage.free_quantity)),
                "штука", "штуки", "штук"
              )}{" "}
              у{" "}
              {withPlural(
                coverage.free_products_count, "товара", "товаров", "товаров"
              )}{" "}
              ушли без оплаты — призы, подарки партнёрам, замены брака,
              пробники. Себестоимость у них настоящая:{" "}
              <b>{formatMoney(coverage.free_cost_kopecks)}</b>, а выручки нет
              вовсе. {coverage.with_free
                ? "Сейчас они посчитаны — поставьте галочку «Без подарков», и маржа поднимется."
                : "Сейчас они не посчитаны — снимите галочку «Без подарков», и маржа опустится."}
            </p>
            {generous.length > 0 ? (
              <>
                <h3 className="mt-1 text-xs text-muted-foreground">
                  На чём подарки стоят дороже всего
                </h3>
                <BarList bars={generous} wideLabels multilineLabels />
              </>
            ) : null}
          </section>
        ) : null}

        <section className="flex flex-col gap-3">
          <h3 className="text-xs text-muted-foreground">Проданное в убыток</h3>
          {losses.length === 0 ? (
            <p className="flex items-start gap-2 text-sm">
              <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-success" />
              <span>
                Ни одного товара не продано дешевле себестоимости.{" "}
                <span className="text-muted-foreground">
                  {coverage.with_free
                    ? "С учётом подарков это уже проверено."
                    : "Снимите галочку «Без подарков» — и в минус уйдут те позиции, что раздавали, а не продавали."}
                </span>
              </span>
            </p>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                {coverage.with_free
                  ? "Часть из них могла уйти даром: у подарка себестоимость есть, а выручки нет. Смотрите колонку «Продано» — там видно, сколько штук роздано."
                  : "Эти позиции продавались дешевле себестоимости. Подарки в расчёт не входят — значит дело в цене."}
              </p>
              <BarList bars={lossBars(losses)} wideLabels multilineLabels />
            </>
          )}
        </section>
      </div>
    </CollapsibleNote>
  )
}

/** Заголовок несёт оба числа: свёрнутый блок обязан оставаться осмысленным. */
function headline(coverage: Profitability["coverage"], losses: number): string {
  const parts: string[] = []
  if (Number(coverage.free_quantity) > 0) {
    parts.push(
      `${formatQuantity(coverage.free_quantity)} шт на ${formatMoney(coverage.free_cost_kopecks)}`
    )
  }
  parts.push(
    losses === 0
      ? "в убыток не продан ни один"
      : `${withPlural(losses, "позиция", "позиции", "позиций")} в минусе`
  )
  return parts.join(", ")
}

/**
 * На чём подарки стоят дороже всего.
 *
 * Список приходит **с сервера**, посчитанный по всей выборке. Собери его
 * фронт по своим строкам — он видел бы только показанную страницу,
 * и лидера в нём могло не оказаться вовсе.
 *
 * **Длина — деньги, а не доля.** Доля выводит наверх мелочь: четыре позиции
 * «Амуниции» роздали целиком, и каждая даёт ровно 100 % при трёх штуках.
 * Четыре одинаковые полосы не отвечают на «кто из них главный» — так
 * и вышло на боевой странице, и нашлось снимком. Доля осталась рядом
 * вторым числом: она объясняет, много это для товара или капля.
 */
function topFree(rows: Profitability["coverage"]["most_given_away"]): Bar[] {
  return rows.slice(0, TOP).map((row) => ({
    key: String(row.product_id),
    label: row.name,
    value: row.free_cost_kopecks,
    display: formatMoney(row.free_cost_kopecks),
    secondary: formatShare(row.share),
    hint: `${formatQuantity(row.free_quantity)} из ${formatQuantity(row.shipped_quantity)} шт отгруженного`,
  }))
}

/** Убыточные позиции. Длина — размер убытка, тон — то, что он убыток. */
function lossBars(losses: ProfitabilityRow[]): Bar[] {
  return losses.slice(0, TOP).map((row) => ({
    key: String(row.product_id),
    label: row.name,
    value: Math.abs(row.profit_kopecks ?? 0),
    display: formatMoney(row.profit_kopecks ?? 0),
    hint:
      (Number(row.free_quantity) > 0
        ? `${formatQuantity(row.free_quantity)} из ${formatQuantity(row.shipped_quantity)} шт роздано · `
        : "") +
      `выручка ${formatMoney(row.revenue_kopecks)}, себестоимость ${formatMoney(row.cost_kopecks ?? 0)}`,
    tone: "destructive" as const,
  }))
}
