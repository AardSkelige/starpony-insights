import type {
  SupplyMaterialDetail,
  SupplyMaterialRow,
} from "@/sections/supplies-materials/api"
import { PriceChange } from "@/sections/supplies-materials/ui/price-change"
import { PriceChart } from "@/sections/supplies-materials/ui/price-line"
import { Fact, Facts, Failed, Loading, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import {
  formatDate,
  formatMoney,
  formatQuantity,
  formatShare,
  formatUnitPrice,
} from "@/shared/lib/format"

/**
 * Итоги строки и цена — два из четырёх блоков разбора.
 *
 * Разбор отвечает на три вопроса, и каждый живёт в своём файле: **цена**
 * объясняет среднюю и динамику (здесь), **закупки** дают слагаемые суммы
 * (`purchase-list.tsx`), **поставщики** отвечают, у кого дешевле
 * (`supplier-list.tsx`). Вместе они складывались в триста с лишним строк —
 * вдвое больше, чем у соседних страниц, и правка одного блока заставляла
 * пролистать остальные.
 *
 * Каждый блок принимает результат запроса целиком, а не разобранные поля:
 * состояний у него четыре — «едет», «не доехало», «нечего показать»,
 * «вот оно», — и каждое выглядит по-своему. О сбое блок говорит только когда
 * он **один в своём месте** (`bare`, то есть за вкладкой): рядом с соседями
 * три одинаковых «Не удалось загрузить» с тремя кнопками повторяли бы
 * один и тот же запрос.
 */
type Detail = {
  isPending: boolean
  isError: boolean
  refetch: () => void
  data?: SupplyMaterialDetail
}

/** Числа самой строки — повторяются в панели, где строка закрыта затемнением. */
export function TotalsSection({ row }: { row: SupplyMaterialRow }) {
  return (
    <Section title="Итоги строки" bare>
      <Facts>
        <Fact label="Закуплено" value={formatQuantity(row.quantity, row.uom)} />
        {Number(row.free_quantity) > 0 ? (
          <Fact
            label="Из них даром"
            value={formatQuantity(row.free_quantity, row.uom)}
          />
        ) : null}
        <Fact
          label="Сумма"
          value={
            row.amount_kopecks > 0 ? formatMoney(row.amount_kopecks) : "—"
          }
        />
        <Fact label="Доля в закупках" value={formatShare(row.amount_share)} />
      </Facts>
    </Section>
  )
}

/**
 * Цена: график ряда, средняя и крайние значения.
 *
 * Средняя приходит вместе с оплаченным количеством, из которого получена,
 * — формула собирается из полученного, а не пересчитывается.
 */
export function PriceSection({
  detail,
  row,
  bare = false,
}: {
  detail: Detail
  row: SupplyMaterialRow
  bare?: boolean
}) {
  return (
    <Section
      title="Цена"
      bare={bare}
      explain={
        <Explain>
          Линия строится <b>по времени</b>, а не по номеру закупки: между
          двумя приёмками бывает два месяца, между следующими — неделя,
          и равные промежутки соврали бы о скорости подорожания. У одной
          закупки линии нет — рисовать нечего.
        </Explain>
      }
    >
      {detail.isPending ? <Loading count={4} /> : null}
      {detail.isError ? <Failed onRetry={detail.refetch} /> : null}

      {detail.data ? (
        <div className="flex min-w-0 flex-col gap-3">
          {/* Линии нет у 130 наименований из 212 — там сразу числа. */}
          <PriceChart prices={row.prices} uom={row.uom} />

          <Facts>
            <Fact
              label="Средняя за период"
              value={
                <span className="inline-flex items-center gap-1.5">
                  {formatUnitPrice(detail.data.avg_price_kopecks)}
                  <Explain>
                    <b>
                      {formatMoney(detail.data.amount_kopecks)} ÷{" "}
                      {formatQuantity(detail.data.paid_quantity, row.uom)}
                    </b>{" "}
                    — в знаменателе оплаченное количество. Бесплатные
                    поступления цену не образуют: у этикетки Табак-Ваниль
                    280 штук из 496 пришли даром, и деление на всё количество
                    занизило бы цену вдвое.
                  </Explain>
                </span>
              }
            />
            <Fact
              label="Последняя закупка"
              value={formatUnitPrice(row.last_price_kopecks)}
            />
            <Fact
              label="Изменение к предыдущей"
              value={
                <PriceChange
                  change={detail.data.price_change}
                  previous={row.previous_price_kopecks}
                  last={row.last_price_kopecks}
                  previousQuantity={row.previous_quantity}
                  lastQuantity={row.last_quantity}
                  uom={row.uom}
                />
              }
            />
            {/* Крайние цены ряда: «дорожает» и «один раз взяли дорого» —
                разные вещи, и эти две строки их различают. */}
            {row.prices.length > 1 ? <Extremes prices={row.prices} /> : null}
          </Facts>
        </div>
      ) : null}
    </Section>
  )
}

function Extremes({ prices }: { prices: SupplyMaterialRow["prices"] }) {
  const sorted = [...prices].sort(
    (left, right) => Number(left.price_kopecks) - Number(right.price_kopecks)
  )
  const cheapest = sorted[0]
  const dearest = sorted[sorted.length - 1]

  return (
    <>
      <Fact
        label="Самая дешёвая"
        value={`${formatUnitPrice(cheapest.price_kopecks)} · ${formatDate(cheapest.moment)}`}
      />
      <Fact
        label="Самая дорогая"
        value={`${formatUnitPrice(dearest.price_kopecks)} · ${formatDate(dearest.moment)}`}
      />
    </>
  )
}
