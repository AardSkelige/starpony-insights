import type {
  ShipmentProductRow,
  useProductDetail,
} from "@/sections/shipments-products/api"
import { BarList, type Bar } from "@/shared/components/bar-list"
import { formatMoney, formatQuantity, formatUnitPrice } from "@/shared/lib/format"
import { Button } from "@/shared/ui/button"
import { Skeleton } from "@/shared/ui/skeleton"

/**
 * Блоки деталей строки.
 *
 * Отдельно от сборки: та решает только, показать их подряд или за
 * переключателем, а что именно внутри каждого — вопрос сам по себе,
 * и меняются они по разным причинам.
 */
type Detail = ReturnType<typeof useProductDetail>

/** Числа самой строки — нужны там, где строка не видна. */
export function PeriodSection({ row, always = false }: { row: ShipmentProductRow; always?: boolean }) {
  const free = Number(row.free_quantity)

  return (
    <Section title="За период" bare={always}>
      <Line label="Продано" value={formatQuantity(row.quantity, row.uom)} />
      {free > 0 ? (
        <Line label="в том числе даром" value={formatQuantity(row.free_quantity)} />
      ) : null}
      <Line label="Выручка" value={formatMoney(row.revenue_kopecks)} />
      <Line label="Средняя за штуку" value={formatUnitPrice(row.avg_price_kopecks)} />
      {free > 0 ? (
        <Line
          label="Без учёта бесплатных"
          value={formatUnitPrice(row.avg_price_paid_kopecks)}
        />
      ) : null}
    </Section>
  )
}

/** Только цена — когда остальные числа видны в раскрытой строке над деталями. */
export function PriceSection({ row }: { row: ShipmentProductRow }) {
  const free = Number(row.free_quantity)

  return (
    <Section title="Цена">
      <Line label="Средняя за штуку" value={formatUnitPrice(row.avg_price_kopecks)} />
      {free > 0 ? (
        <Line
          label="Без учёта бесплатных"
          value={formatUnitPrice(row.avg_price_paid_kopecks)}
        />
      ) : null}
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
      {detail.isPending ? <Lines count={4} /> : <BarList bars={bars} />}
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
        <Lines count={3} />
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
                {shortDate(document.moment)}
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

export function StockSection({ detail }: { detail: Detail }) {
  if (detail.isPending) {
    return (
      <Section title="Склад">
        <Lines count={2} />
      </Section>
    )
  }

  // Молчать об ошибке здесь безопаснее: остаток известен не по всем товарам,
  // и его отсутствие — обычное дело. Ошибку уже показали соседние блоки.
  const stock = detail.data?.stock
  // Нули вместо остатка читались бы как «кончился», поэтому блока просто нет.
  if (!stock) return null

  return (
    <Section title="Склад">
      <Line label="Остаток" value={formatQuantity(stock.quantity)} />
      <Line label="В резерве" value={formatQuantity(stock.reserved)} />
      <Line label="Свободно" value={formatQuantity(stock.available)} />
      {stock.stock_days !== null ? (
        <Line label="Без движения" value={`${stock.stock_days} дн.`} />
      ) : null}
    </Section>
  )
}

/** Данные не доехали. Кнопка повтора обязательна: иначе тупик. */
function Failed({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <span className="text-muted-foreground">Не удалось загрузить</span>
      <Button variant="outline" size="xs" onClick={onRetry}>
        Повторить
      </Button>
    </div>
  )
}

function Section({
  title,
  children,
  bare = false,
}: {
  title: string
  children: React.ReactNode
  bare?: boolean
}) {
  return (
    <div className="min-w-0">
      {/* За вкладкой заголовок лишний: его роль играет сама вкладка. */}
      {bare ? null : (
        <div className="mb-2 flex items-center gap-2">
          <span className="text-xs tracking-wide text-muted-foreground uppercase">
            {title}
          </span>
          <span className="h-px flex-1 bg-border" />
        </div>
      )}
      <dl className="flex flex-col">{children}</dl>
    </div>
  )
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b py-1.5 text-sm last:border-b-0">
      <dt className="min-w-0 text-muted-foreground">{label}</dt>
      {/* Число не ужимается и не переносится — уступает подпись. */}
      <dd className="shrink-0 tabular-nums">{value}</dd>
    </div>
  )
}

/** Скелетон повторяет форму содержимого: строки той же высоты. */
function Lines({ count }: { count: number }) {
  return (
    <div className="flex flex-col gap-2 py-1">
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton key={index} className="h-4 w-full" />
      ))}
    </div>
  )
}

function shortDate(iso: string): string {
  const date = new Date(iso)
  return `${String(date.getDate()).padStart(2, "0")}.${String(date.getMonth() + 1).padStart(2, "0")}`
}
