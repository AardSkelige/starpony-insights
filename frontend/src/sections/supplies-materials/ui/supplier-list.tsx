import type {
  SupplierPrice,
  SupplyMaterialDetail,
  SupplyMaterialRow,
} from "@/sections/supplies-materials/api"
import { Failed, Loading, Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatDate, formatShare, formatUnitPrice } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/** Состояния запроса разбора — те же четыре, что у соседних блоков. */
type Detail = {
  isPending: boolean
  isError: boolean
  refetch: () => void
  data?: SupplyMaterialDetail
}

/**
 * Поставщики: у кого дешевле.
 *
 * Сравниваются **последние** цены поставщиков, а не крайние цены вообще.
 * Иначе у «Крышки флип-топ» разброс 73 % оказался бы между «Лемуном»
 * и «Лемуном» — это движение цены во времени, а не разница между
 * поставщиками, и решение «уйти к другому» на нём не построить.
 */
export function SuppliersSection({
  detail,
  row,
  bare = false,
}: {
  detail: Detail
  row: SupplyMaterialRow
  bare?: boolean
}) {
  const rows = detail.data?.suppliers ?? []

  return (
    <Section
      title="У кого дешевле"
      bare={bare}
      explain={
        <Explain>
          Сравниваются <b>последние</b> цены поставщиков, а не крайние цены
          вообще. Иначе у «Крышки флип-топ» разброс 73 % оказался бы между
          «Лемуном» и «Лемуном» — это движение цены во времени, а не разница
          между поставщиками. Поставщик, у которого материал приходил только
          даром, в сравнении не участвует: подарок — не предложение.
        </Explain>
      }
      note={
        detail.data && rows.length === 1
          ? "Материал брали у одного поставщика — сравнивать не с кем."
          : undefined
      }
    >
      {detail.isPending ? <Loading count={3} /> : null}
      {detail.isError ? <Failed onRetry={detail.refetch} /> : null}

      {detail.data ? (
        <div className="flex min-w-0 flex-col">
          {rows.map((supplier) => (
            <SupplierRow key={supplier.supplier_id} supplier={supplier} uom={row.uom} />
          ))}
        </div>
      ) : null}
    </Section>
  )
}

function SupplierRow({
  supplier,
  uom,
}: {
  supplier: SupplierPrice
  uom: string
}) {
  return (
    <div className="flex min-w-0 items-baseline gap-3 border-b py-1.5 text-sm last:border-b-0">
      <span className="min-w-0 flex-1">
        <span className="block truncate">{supplier.name}</span>
        <span className="text-xs text-muted-foreground">
          {withPlural(supplier.supplies_count, "закупка", "закупки", "закупок")}
          {supplier.last_moment ? ` · ${formatDate(supplier.last_moment)}` : ""}
        </span>
      </span>
      <span className="shrink-0 tabular-nums">
        {supplier.last_price_kopecks === null ? (
          // Поставщик, у которого материал приходил только даром, в сравнении
          // цен не участвует: подарок — не предложение.
          <span className="text-muted-foreground">только даром</span>
        ) : (
          <>
            {formatUnitPrice(supplier.last_price_kopecks)}/{uom || "ед."}
          </>
        )}
      </span>
      <span className="w-20 shrink-0 text-right text-xs tabular-nums">
        {supplier.above_best === null ? (
          <span className="text-muted-foreground">—</span>
        ) : Number(supplier.above_best) === 0 ? (
          <span className="font-medium text-success">дешевле всех</span>
        ) : (
          <span className="font-medium text-destructive">
            +{formatShare(supplier.above_best)}
          </span>
        )}
      </span>
    </div>
  )
}
