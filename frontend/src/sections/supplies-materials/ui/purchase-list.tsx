import type {
  Purchase,
  SupplyMaterialDetail,
  SupplyMaterialRow,
} from "@/sections/supplies-materials/api"
import { PriceChange } from "@/sections/supplies-materials/ui/price-change"
import { Failed, Loading, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatDate, formatMoney, formatQuantity, formatUnitPrice } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/** Состояния запроса разбора — те же четыре, что у соседних блоков. */
type Detail = {
  isPending: boolean
  isError: boolean
  refetch: () => void
  data?: SupplyMaterialDetail
}

/**
 * Закупки: слагаемые суммы строки.
 *
 * Хронологически, от старой к новой: история цен читается слева направо,
 * и «свежее сверху» ломало бы ровно то, ради чего её открыли.
 */
export function PurchasesSection({
  detail,
  row,
  bare = false,
}: {
  detail: Detail
  row: SupplyMaterialRow
  bare?: boolean
}) {
  const rows = detail.data?.history ?? []

  return (
    <Section
      title="Закупки"
      bare={bare}
      explain={
        <Explain>
          <b>Закупка — это приёмка, а не строка в ней.</b> Один материал
          приходит одним документом двумя партиями: считай мы строками,
          у диметилфталата вышло бы шесть закупок вместо пяти и скачок цены
          внутри одного дня. Цена документа — средневзвешенная.
        </Explain>
      }
      note={
        detail.data
          ? `${withPlural(rows.length, "приёмка", "приёмки", "приёмок")} — суммы складываются в ${formatMoney(detail.data.amount_kopecks)}`
          : undefined
      }
    >
      {detail.isPending ? <Loading count={5} /> : null}
      {detail.isError ? <Failed onRetry={detail.refetch} /> : null}

      {detail.data ? (
        <div className="flex min-w-0 flex-col">
          {rows.map((purchase, index) => (
            <PurchaseRow
              key={purchase.document_id}
              purchase={purchase}
              // Предыдущая приёмка **с ценой**, а не просто предыдущая:
              // между двумя платными стоит бесплатная допечатка, и подсказка
              // «даром → 1,70 ₽» говорила бы о росте с нуля.
              before={previousPriced(rows, index)}
              uom={row.uom}
            />
          ))}
        </div>
      ) : null}
    </Section>
  )
}

/** Предыдущая приёмка с ценой — та, с которой сервер и считал процент. */
function previousPriced(rows: Purchase[], index: number): Purchase | null {
  for (let step = index - 1; step >= 0; step -= 1) {
    if (!rows[step].is_free) return rows[step]
  }
  return null
}

/**
 * Одна приёмка. Дата, номер и поставщик сверху, количество и цена снизу.
 *
 * Не четырьмя колонками фиксированной ширины в одну строку: на 390 точках
 * такая строка не сходится, и значения уезжают за край — это уже случилось
 * на «Товарах в отгрузках» (`DESIGN.md` §15).
 */
function PurchaseRow({
  purchase,
  before,
  uom,
}: {
  purchase: Purchase
  before: Purchase | null
  uom: string
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 border-b py-1.5 last:border-b-0">
      <div className="flex min-w-0 items-baseline gap-2 text-xs text-muted-foreground">
        <span className="shrink-0 font-mono tabular-nums">
          {formatDate(purchase.moment)}
        </span>
        <span className="shrink-0 font-mono">№{purchase.number}</span>
        <span className="min-w-0 truncate">{purchase.supplier}</span>
      </div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="flex min-w-0 items-center gap-2 text-muted-foreground">
          <span className="shrink-0 tabular-nums">
            {formatQuantity(purchase.quantity, uom)}
          </span>
          {purchase.price_change !== null ? (
            <PriceChange
              change={purchase.price_change}
              previous={before?.price_kopecks ?? null}
              last={purchase.price_kopecks}
              previousQuantity={before?.quantity ?? null}
              lastQuantity={purchase.quantity}
              uom={uom}
            />
          ) : null}
        </span>
        <span className="shrink-0 tabular-nums">
          {/* «Даром», а не «0,00 ₽»: ноль читался бы как цена, и средняя
              по столбцу, посчитанная глазом, разошлась бы с итогом. */}
          {purchase.is_free ? (
            <span className="text-muted-foreground">даром</span>
          ) : (
            <>
              {formatUnitPrice(purchase.price_kopecks)} ·{" "}
              <span className="font-medium">
                {formatMoney(purchase.amount_kopecks)}
              </span>
            </>
          )}
        </span>
      </div>
    </div>
  )
}
