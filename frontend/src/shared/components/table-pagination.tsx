import { MoreHorizontal } from "lucide-react"

import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/shared/ui/pagination"
import { pagesToShow } from "@/shared/lib/pagination"

/**
 * Постраничная навигация с русскими подписями.
 *
 * Своя обёртка, а не правка компонента реестра: его обновляет CLI, и любое
 * изменение внутри потерялось бы при следующем `shadcn add`. Подписи «Previous»
 * и «Next» вынесены в пропы самим компонентом, а вот многоточие несёт
 * зашитое «More pages» для читалок экрана — поэтому оно нарисовано здесь.
 */
export function TablePagination({
  page,
  pageCount,
  onChange,
}: {
  page: number
  pageCount: number
  onChange: (page: number) => void
}) {
  if (pageCount <= 1) return null

  return (
    <Pagination className="mx-0 w-auto justify-end">
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious
            text="Назад"
            aria-label="Предыдущая страница"
            aria-disabled={page <= 1}
            className={page <= 1 ? "pointer-events-none opacity-50" : undefined}
            onClick={() => onChange(page - 1)}
          />
        </PaginationItem>

        {pagesToShow(page, pageCount).map((item, index) =>
          item === null ? (
            <PaginationItem key={`gap-${index}`}>
              <span
                aria-hidden
                className="flex size-8 items-center justify-center text-muted-foreground"
              >
                <MoreHorizontal className="size-4" />
              </span>
              <span className="sr-only">Пропущенные страницы</span>
            </PaginationItem>
          ) : (
            <PaginationItem key={item}>
              <PaginationLink
                isActive={item === page}
                aria-label={`Страница ${item}`}
                onClick={() => onChange(item)}
              >
                {item}
              </PaginationLink>
            </PaginationItem>
          )
        )}

        <PaginationItem>
          <PaginationNext
            text="Вперёд"
            aria-label="Следующая страница"
            aria-disabled={page >= pageCount}
            className={page >= pageCount ? "pointer-events-none opacity-50" : undefined}
            onClick={() => onChange(page + 1)}
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  )
}
