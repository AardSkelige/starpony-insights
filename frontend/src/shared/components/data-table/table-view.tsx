import { ArrowDown, ArrowUp, ArrowUpDown, ChevronRight } from "lucide-react"

import type { Column, Sort, Totals } from "@/shared/components/data-table/columns"
import { cn } from "@/shared/lib/utils"
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table"

type Props<Row> = {
  columns: Column<Row>[]
  rows: Row[]
  rowKey: (row: Row) => string | number
  /** Раскрытие строки на месте — вид деталей для широкого экрана. */
  renderDetail?: (row: Row) => React.ReactNode
  expandedKey?: string | number | null
  onToggle?: (row: Row) => void
  totals?: Totals
  sort?: Sort | null
  onSort?: (key: string, numeric: boolean) => void
  muted?: boolean
}

export function TableView<Row>({
  columns,
  rows,
  rowKey,
  renderDetail,
  expandedKey,
  onToggle,
  totals,
  sort,
  onSort,
  muted = false,
}: Props<Row>) {
  const expandable = Boolean(renderDetail)

  return (
    // Таблица шире экрана прокручивается внутри себя: горизонтальная полоса
    // у всей страницы уводила бы вместе с таблицей и шапку с фильтрами.
    <div className="overflow-x-auto rounded-lg border">
      <Table className={cn(muted && "opacity-60 transition-opacity")}>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {columns.map((column) => {
              const sortable = Boolean(column.sortKey && onSort)
              const active = sortable && sort?.key === column.sortKey

              return (
                <TableHead
                  key={column.key}
                  className={cn(
                    "text-xs font-normal tracking-wide text-muted-foreground uppercase",
                    column.numeric && "text-right"
                  )}
                  aria-sort={
                    active ? (sort?.desc ? "descending" : "ascending") : undefined
                  }
                >
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5",
                      column.numeric && "flex-row-reverse"
                    )}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => onSort?.(column.sortKey!, Boolean(column.numeric))}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-sm transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                          column.numeric && "flex-row-reverse",
                          active && "text-foreground"
                        )}
                      >
                        {column.label}
                        {/* Значок стоит у каждой сортируемой колонки, а не
                            только у активной: иначе о самой возможности
                            сортировать узнают случайным щелчком. */}
                        {active ? (
                          sort?.desc ? (
                            <ArrowDown className="size-3" />
                          ) : (
                            <ArrowUp className="size-3" />
                          )
                        ) : (
                          <ArrowUpDown className="size-3 opacity-40" />
                        )}
                      </button>
                    ) : (
                      column.label
                    )}
                    {column.explain}
                  </span>
                </TableHead>
              )
            })}
          </TableRow>
        </TableHeader>

        <TableBody>
          {rows.map((row) => {
            const key = rowKey(row)
            const open = expandable && expandedKey === key

            return [
              <TableRow
                key={key}
                aria-expanded={expandable ? open : undefined}
                // Подсветку раскрытой строки включает `data-state`, а не
                // `aria-expanded`: компонент реестра красит по нему потомка
                // (`has-aria-expanded` — это `:has([aria-expanded])`), и атрибут
                // на самой строке под правило не попадает. Сам `aria-expanded`
                // остаётся: он нужен читалкам экрана.
                data-state={open ? "selected" : undefined}
                onClick={expandable ? () => onToggle?.(row) : undefined}
                className={cn(
                  expandable && "cursor-pointer",
                  // Наведение и выбор — разные состояния, и выбор должен
                  // побеждать: иначе, наведя курсор на раскрытую строку,
                  // человек видит тот же фон, что у любой соседней.
                  open && "bg-accent hover:bg-accent"
                )}
              >
                {columns.map((column, index) => (
                  <TableCell
                    key={column.key}
                    className={cn(
                      column.numeric && "text-right tabular-nums",
                      column.strong && "font-medium"
                    )}
                  >
                    {index === 0 && expandable ? (
                      <span className="flex items-center gap-2">
                        <ChevronRight
                          aria-hidden
                          className={cn(
                            "size-3.5 shrink-0 text-muted-foreground transition-transform",
                            open && "rotate-90"
                          )}
                        />
                        <span className="min-w-0">{column.render(row)}</span>
                      </span>
                    ) : (
                      column.render(row)
                    )}
                  </TableCell>
                ))}
              </TableRow>,

              open ? (
                <TableRow key={`${key}-detail`} className="hover:bg-transparent">
                  <TableCell colSpan={columns.length} className="bg-accent/40 p-0">
                    {renderDetail?.(row)}
                  </TableCell>
                </TableRow>
              ) : null,
            ]
          })}
        </TableBody>

        {totals ? (
          <TableFooter>
            <TableRow className="hover:bg-transparent">
              {columns.map((column, index) => (
                <TableCell
                  key={column.key}
                  className={cn(column.numeric && "text-right tabular-nums")}
                >
                  {index === 0 ? totals.label : (totals.values[column.key] ?? null)}
                </TableCell>
              ))}
            </TableRow>
          </TableFooter>
        ) : null}
      </Table>
    </div>
  )
}
