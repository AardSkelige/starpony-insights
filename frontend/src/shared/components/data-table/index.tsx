import type { Column, Sort, Totals } from "@/shared/components/data-table/columns"
import { visibleColumns } from "@/shared/components/data-table/columns"
import { CardView } from "@/shared/components/data-table/card-view"
import { TableView } from "@/shared/components/data-table/table-view"
import { useChangedCells } from "@/shared/components/data-table/use-changed-cells"
import { EmptyState, ErrorState } from "@/shared/components/states"
import { useScreen } from "@/shared/hooks/use-screen"
import { Skeleton } from "@/shared/ui/skeleton"

export type { Column, Sort, Totals } from "@/shared/components/data-table/columns"
export {
  DEFAULT_PAGE_SIZE,
  PAGE_SIZES,
} from "@/shared/components/data-table/columns"

type Props<Row> = {
  columns: Column<Row>[]
  rows: Row[]
  rowKey: (row: Row) => string | number

  /** Первая загрузка: показывается скелетон. */
  loading?: boolean
  /** Повторная: старые данные приглушаются, но остаются на экране. */
  refreshing?: boolean
  /** Синхронизация с МойСкладом — единственный источник подсветки чисел.
   *  Чужой прогон считается наравне со своим: его так же видно в шапке. */
  syncPending?: boolean
  syncFailed?: boolean
  /** Время последнего успешного ответа React Query. */
  dataVersion?: number
  error?: boolean
  onRetry?: () => void

  emptyTitle: string
  emptyHint: string

  /** Раскрытие строки на месте — широкий экран. */
  renderDetail?: (row: Row) => React.ReactNode
  expandedKey?: string | number | null
  onToggle?: (row: Row) => void
  /** Открыть детали панелью — узкий экран и телефон. */
  onOpen?: (row: Row) => void

  totals?: Totals
  sort?: Sort | null
  onSort?: (key: string, numeric: boolean) => void
}

/**
 * Таблица раздела: сама выбирает вид по ширине экрана и сама показывает
 * загрузку, ошибку и пустое состояние.
 *
 * Скелетон — только при первой загрузке. При повторной старые данные
 * приглушаются: показать скелетон вместо них значит на секунду отобрать
 * у человека то, что он уже читал.
 */
export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  loading = false,
  refreshing = false,
  syncPending = false,
  syncFailed = false,
  dataVersion = 0,
  error = false,
  onRetry,
  emptyTitle,
  emptyHint,
  renderDetail,
  expandedKey,
  onToggle,
  onOpen,
  totals,
  sort,
  onSort,
}: Props<Row>) {
  const screen = useScreen()
  const shown = visibleColumns(columns, screen)
  const changedCells = useChangedCells({
    columns,
    rows,
    rowKey,
    syncPending,
    syncFailed,
    dataVersion,
    selectionChanging: refreshing,
  })

  if (error) {
    return <ErrorState onRetry={onRetry ?? (() => {})} />
  }

  if (loading) {
    return <TableSkeleton columns={shown.length} />
  }

  if (rows.length === 0) {
    return <EmptyState title={emptyTitle} hint={emptyHint} />
  }

  if (screen === "phone") {
    return (
      <CardView
        columns={shown}
        rows={rows}
        rowKey={rowKey}
        onOpen={onOpen}
        totals={totals}
        muted={refreshing}
        changedCells={changedCells}
      />
    )
  }

  return (
    <TableView
      columns={shown}
      rows={rows}
      rowKey={rowKey}
      // Раскрытие строки — только на широком экране. На узком места под детали
      // в строке нет, и они открываются панелью сбоку.
      renderDetail={screen === "wide" ? renderDetail : undefined}
      expandedKey={expandedKey}
      onToggle={screen === "wide" ? onToggle : onOpen}
      totals={totals}
      sort={sort}
      onSort={onSort}
      muted={refreshing}
      changedCells={changedCells}
    />
  )
}

/** Скелетон повторяет форму содержимого: шапка и строки той же ширины. */
function TableSkeleton({ columns }: { columns: number }) {
  return (
    <div className="motion-content-reveal flex flex-col gap-2 rounded-lg border p-3">
      {Array.from({ length: 8 }).map((_, row) => (
        <div key={row} className="flex items-center gap-3">
          <Skeleton className="h-4 flex-1" />
          {Array.from({ length: Math.max(0, columns - 1) }).map((__, cell) => (
            <Skeleton key={cell} className="h-4 w-16" />
          ))}
        </div>
      ))}
    </div>
  )
}
