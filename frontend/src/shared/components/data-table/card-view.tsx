import type { Column, Totals } from "@/shared/components/data-table/columns"
import { changedCellKey } from "@/shared/components/data-table/changes"
import { cn } from "@/shared/lib/utils"

type Props<Row> = {
  columns: Column<Row>[]
  rows: Row[]
  rowKey: (row: Row) => string | number
  onOpen?: (row: Row) => void
  totals?: Totals
  muted?: boolean
  changedCells?: Set<string>
}

/**
 * Вид таблицы на телефоне: строка на карточку.
 *
 * Всё в столбик — подпись слева, значение справа, каждое на своей строке.
 * Две колонки пар не годятся: «Выручка 231 530,38 ₽» набрана неразрывными
 * пробелами и не переносится, поэтому распирает ячейку и уезжает за край.
 *
 * Название переносится целиком, а не прячется за многоточие: в списке
 * из шестидесяти шести позиций «Кондиционер для гривы и хвоста Сияющ…»
 * не отличить от соседа, у которого те же первые сорок знаков.
 */
export function CardView<Row>({
  columns,
  rows,
  rowKey,
  onOpen,
  totals,
  muted = false,
  changedCells = new Set(),
}: Props<Row>) {
  const [title, ...rest] = columns

  return (
    <div
      className={cn(
        "motion-content-reveal motion-opacity-transition flex flex-col gap-2",
        muted && "opacity-60"
      )}
    >
      {rows.map((row) => {
        const key = rowKey(row)
        return (
          <button
            key={key}
            type="button"
            onClick={onOpen ? () => onOpen(row) : undefined}
            disabled={!onOpen}
            className="flex flex-col gap-2.5 rounded-xl border bg-card p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring active:bg-accent disabled:pointer-events-none"
          >
            <div
              className={cn(
                "min-w-0 rounded-sm",
                changedCells.has(changedCellKey(key, title.key)) &&
                  "motion-data-flash"
              )}
            >
              {title.render(row)}
            </div>
            <dl className="flex flex-col">
              {rest.map((column) => (
                <div
                  key={column.key}
                  className={cn(
                    "flex items-baseline justify-between gap-3 rounded-sm border-b py-1.5 text-sm last:border-b-0",
                    changedCells.has(changedCellKey(key, column.key)) &&
                      "motion-data-flash"
                  )}
                >
                  <dt className="min-w-0 text-muted-foreground">
                    {column.cardLabel ?? column.label}
                  </dt>
                  {/* Число не переносится и не ужимается: подпись слева
                    уступит место первой, ей есть куда. */}
                  <dd className="shrink-0 tabular-nums">
                    {column.render(row)}
                  </dd>
                </div>
              ))}
            </dl>
          </button>
        )
      })}

      {totals ? (
        <div className="flex flex-col gap-2.5 rounded-xl border bg-muted/40 p-3">
          <div className="text-sm font-medium">{totals.label}</div>
          <dl className="flex flex-col">
            {rest.map((column) =>
              totals.values[column.key] ? (
                <div
                  key={column.key}
                  className="flex items-baseline justify-between gap-3 border-b py-1.5 text-sm last:border-b-0"
                >
                  <dt className="min-w-0 text-muted-foreground">
                    {column.cardLabel ?? column.label}
                  </dt>
                  <dd className="shrink-0 tabular-nums">
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
