import type { Column, Totals } from "@/shared/components/data-table/columns"
import { cn } from "@/shared/lib/utils"

type Props<Row> = {
  columns: Column<Row>[]
  rows: Row[]
  rowKey: (row: Row) => string | number
  onOpen?: (row: Row) => void
  totals?: Totals
  muted?: boolean
}

/**
 * Вид таблицы на телефоне: строка на карточку.
 *
 * Таблицу в пять колонок на экране шириной 390 точек читать нечем — она либо
 * уезжает вбок, либо схлопывается в нечитаемые столбцы. Карточка показывает
 * ту же строку сверху вниз: первая колонка заголовком, остальные парами
 * «подпись — значение».
 */
export function CardView<Row>({ columns, rows, rowKey, onOpen, totals, muted = false }: Props<Row>) {
  const [title, ...rest] = columns

  return (
    <div className={cn("flex flex-col gap-2", muted && "opacity-60 transition-opacity")}>
      {rows.map((row) => (
        <button
          key={rowKey(row)}
          type="button"
          onClick={onOpen ? () => onOpen(row) : undefined}
          disabled={!onOpen}
          className="flex flex-col gap-2 rounded-lg border bg-card p-3 text-left transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none"
        >
          <div className="font-medium">{title.render(row)}</div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
            {rest.map((column) => (
              <div key={column.key} className="flex items-baseline justify-between gap-2">
                <dt className="text-xs text-muted-foreground">
                  {column.cardLabel ?? column.label}
                </dt>
                <dd className="text-sm tabular-nums">{column.render(row)}</dd>
              </div>
            ))}
          </dl>
        </button>
      ))}

      {totals ? (
        <div className="flex flex-col gap-2 rounded-lg border bg-muted/40 p-3">
          <div className="text-sm font-medium">{totals.label}</div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
            {rest.map((column) =>
              totals.values[column.key] ? (
                <div key={column.key} className="flex items-baseline justify-between gap-2">
                  <dt className="text-xs text-muted-foreground">
                    {column.cardLabel ?? column.label}
                  </dt>
                  <dd className="text-sm tabular-nums">
                    {totals.values[column.key]}
                  </dd>
                </div>
              ) : null
            )}
          </dl>
        </div>
      ) : null}
    </div>
  )
}
