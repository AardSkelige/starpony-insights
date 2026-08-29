import type {
  ShipmentProductRow,
  useProductDetail,
} from "@/sections/shipments-products/api"
import { BarList, type Bar } from "@/shared/components/bar-list"
import {
  Fact,
  Facts,
  Failed,
  Loading,
  Section,
} from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import {
  formatDayMonth,
  formatMoney,
  formatQuantity,
  formatUnitPrice,
} from "@/shared/lib/format"

/**
 * Блоки деталей строки.
 *
 * Отдельно от сборки: та решает только, показать их подряд или за
 * переключателем, а что именно внутри каждого — вопрос сам по себе,
 * и меняются они по разным причинам.
 */
type Detail = ReturnType<typeof useProductDetail>

/** Числа самой строки — нужны там, где строка не видна. */
export function PeriodSection({
  row,
  always = false,
}: {
  row: ShipmentProductRow
  always?: boolean
}) {
  const free = Number(row.free_quantity)

  return (
    <Section title="За период" bare={always}>
      <Facts>
        <Fact label="Продано" value={formatQuantity(row.quantity, row.uom)} />
        {free > 0 ? (
          <Fact
            label="в том числе даром"
            value={formatQuantity(row.free_quantity)}
          />
        ) : null}
        <Fact label="Выручка" value={formatMoney(row.revenue_kopecks)} />
        <Fact
          label="Средняя за штуку"
          value={formatUnitPrice(row.avg_price_kopecks)}
        />
        {free > 0 ? (
          <Fact
            label="Без учёта бесплатных"
            value={formatUnitPrice(row.avg_price_paid_kopecks)}
          />
        ) : null}
      </Facts>
    </Section>
  )
}

/** Только цена — когда остальные числа видны в раскрытой строке над деталями. */
export function PriceSection({ row }: { row: ShipmentProductRow }) {
  const free = Number(row.free_quantity)

  return (
    <Section
      title="Цена"
      explain={
        <Explain>
          <b>Выручка ÷ количество</b> по выбранной выборке. Отгрузки за 0 ₽
          в делении участвуют: 532 штуки из 2338 ушли даром, и средняя
          из-за них ниже той, по которой действительно продавали.
        </Explain>
      }
    >
      <Facts>
        <Fact
          label="Средняя за штуку"
          value={formatUnitPrice(row.avg_price_kopecks)}
        />
        {free > 0 ? (
          <Fact
            label="Без учёта бесплатных"
            value={formatUnitPrice(row.avg_price_paid_kopecks)}
          />
        ) : null}
      </Facts>
    </Section>
  )
}

export function ChannelsSection({
  detail,
  uom,
  bare = false,
}: {
  detail: Detail
  uom: string
  bare?: boolean
}) {
  const channels = detail.data?.channels ?? []

  // Сбой не должен выглядеть как «каналов нет»: пустой блок читается
  // как факт об учёте, хотя на деле данные просто не доехали.
  if (detail.isError) {
    return (
      <Section title="По каналам продаж" bare={bare}>
        <Failed onRetry={() => detail.refetch()} />
      </Section>
    )
  }

  // Одна полоса не сравнение: при фильтре по конкретному каналу разбивка
  // вырождается в саму строку и ничего не добавляет.
  if (!detail.isPending && channels.length < 2) {
    if (!bare) return null
    return (
      <Section title="По каналам продаж" bare>
        <p className="py-1.5 text-sm text-muted-foreground">
          Весь товар ушёл по одному каналу.
        </p>
      </Section>
    )
  }

  const bars: Bar[] = channels.map((channel) => ({
    key: String(channel.id ?? channel.name),
    label: channel.name,
    value: Number(channel.quantity),
    display: formatQuantity(channel.quantity),
    hint: `${channel.name}: ${formatQuantity(channel.quantity, uom)} на ${formatMoney(channel.revenue_kopecks)}`,
  }))

  return (
    <Section title="По каналам продаж" bare={bare}>
      {detail.isPending ? <Loading count={4} /> : <BarList bars={bars} />}
    </Section>
  )
}

export function DocumentsSection({
  detail,
  count,
  bare = false,
}: {
  detail: Detail
  count: number
  bare?: boolean
}) {
  const documents = detail.data?.documents ?? []

  return (
    <Section title={`Последние отгрузки · всего ${count}`} bare={bare}>
      {detail.isError ? (
        <Failed onRetry={() => detail.refetch()} />
      ) : detail.isPending ? (
        <Loading count={3} />
      ) : (
        <div className="flex flex-col">
          {documents.map((document) => (
            <div
              key={`${document.number}-${document.moment}`}
              className="flex items-baseline gap-2 border-b py-1.5 text-sm last:border-b-0"
            >
              <span className="shrink-0 font-mono text-xs text-muted-foreground">
                {document.number}
              </span>
              <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                {formatDayMonth(document.moment)}
              </span>
              {/* Имя контрагента — единственное, чем можно пожертвовать:
                  числа не переносятся, а «ООО „Коноспортивный центр…“»
                  читается и в укороченном виде. */}
              <span className="min-w-0 flex-1 truncate">{document.agent}</span>
              <span className="shrink-0 tabular-nums">
                {formatQuantity(document.quantity)}
              </span>
              <span className="shrink-0 tabular-nums">
                {formatMoney(document.total_kopecks)}
              </span>
            </div>
          ))}
        </div>
      )}
    </Section>
  )
}