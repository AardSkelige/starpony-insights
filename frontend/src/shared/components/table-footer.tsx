import { PageSize } from "@/shared/components/page-size"
import { TablePagination } from "@/shared/components/table-pagination"

/**
 * Подвал таблицы: сколько всего, сколько строк на странице, листалка.
 *
 * Собран в одном месте, потому что порядок этих трёх вещей должен совпадать
 * на всех разделах: человек за день открывает три-четыре страницы и не должен
 * каждый раз искать, где здесь переключатель высоты.
 */
export function TableFooter({
  summary,
  page,
  pageCount,
  pageSize,
  onPage,
  onPageSize,
}: {
  /** Что в выборке: «161 материал · 294 отгрузки». */
  summary: React.ReactNode
  page: number
  pageCount: number
  pageSize: number
  onPage: (page: number) => void
  onPageSize: (size: number) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-xs text-muted-foreground">{summary}</span>
      <PageSize value={pageSize} onChange={onPageSize} />
      <div className="ml-auto">
        <TablePagination page={page} pageCount={pageCount} onChange={onPage} />
      </div>
    </div>
  )
}
