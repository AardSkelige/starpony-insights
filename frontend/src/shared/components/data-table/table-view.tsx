import * as React from "react"
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronRight } from "lucide-react"

import { changedCellKey } from "@/shared/components/data-table/changes"
import type { Column, Sort, Totals } from "@/shared/components/data-table/columns"
import { DetailRow } from "@/shared/components/data-table/detail-row"
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

/**
 * Первая колонка берёт всю оставшуюся ширину и **отдаёт** её остальным.
 *
 * `max-w-0` вместе с `w-full` — единственный способ заставить обрезку
 * и перенос работать внутри `table-layout: auto`. Без него браузер считает
 * предпочтительную ширину колонки по самому длинному названию и растягивает
 * таблицу за край экрана: «Этикетка | Задняя | Кондиционер для гривы
 * и хвоста Peachy Banana 500 мл (Старое)» уводила колонку «Закупок»
 * в горизонтальную прокрутку, хотя места на экране было вдвое больше нужного.
 *
 * Применяется и к шапке, и к строкам, и к подвалу: хватит одной ячейки
 * без ограничения, чтобы колонка снова растянулась.
 */
// Колонка имени забирает всю свободную ширину (`w-full max-w-0`), но ниже
// `min-w` не опускается. Без нижней границы на узком экране она схлопывалась
// до полутора сотен точек, и семь строк подряд читались как «Кондиционер для
// гривы и хвоста…» — неотличимо друг от друга. Таблица и так прокручивается
// внутри себя, и горизонтальная полоса честнее, чем список одинаковых строк.
const NAME_CELL = "w-full min-w-56 max-w-0"

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
  changedCells?: Set<string>
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
  changedCells = new Set(),
}: Props<Row>) {
  // Раскрывается ли строка **внутри таблицы**: стрелка и полоса разбора
  // под строкой. Только на широком экране — на узком разбор показывается
  // выдвижной панелью, и `renderDetail` сюда не передаётся вовсе.
  const expandable = Boolean(renderDetail)

  // Реагирует ли строка на щелчок. Отдельно от `expandable`, и это не
  // придирка: на узком экране разбора внутри таблицы нет, но строка обязана
  // открывать панель. Пока условие было общим, `onClick` не вешался вовсе —
  // и на 900 точках разбор был недостижим **на всех пяти страницах** сразу,
  // молча: ни ошибки, ни курсора, ни признака, что строка вообще живая.
  // Нашлось снимками, ни один тест такого не видит.
  const clickable = Boolean(onToggle)

  // Ключ строки, которая сейчас схлопывается. Раскрытая строка одна, значит
  // и закрывающаяся одна: держать здесь множество нечего.
  //
  // Прошлый ключ живёт в состоянии, а не в ссылке: правка при рендере — тот
  // самый случай, для которого React держит этот приём, а ссылку в нём читать
  // нельзя (`react-hooks/refs` ловит это в линтере).
  const opened = expandedKey ?? null
  const [tracked, setTracked] = React.useState<{
    opened: string | number | null
    collapsing: string | number | null
  }>({ opened, collapsing: null })

  if (tracked.opened !== opened) {
    // Закрытие обязано застать разбор ещё смонтированным, иначе схлопывать
    // нечего: прошлый ключ переезжает в `collapsing` до следующего кадра.
    setTracked({ opened, collapsing: tracked.opened })
  }
  const collapsing = tracked.collapsing

  return (
    // Таблица шире экрана прокручивается внутри себя: горизонтальная полоса
    // у всей страницы уводила бы вместе с таблицей и шапку с фильтрами.
    <div className="motion-content-reveal overflow-x-auto rounded-lg border">
      <Table className={cn("motion-opacity-transition", muted && "opacity-60")}>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {columns.map((column, index) => {
              const sortable = Boolean(column.sortKey && onSort)
              const active = sortable && sort?.key === column.sortKey

              return (
                <TableHead
                  key={column.key}
                  className={cn(
                    "text-xs font-normal tracking-wide text-muted-foreground uppercase",
                    column.numeric && "text-right",
                    index === 0 && NAME_CELL
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
                          // `uppercase` обязателен здесь, хотя он уже задан
                          // у `TableHead`: `button` не наследует
                          // `text-transform`, и заголовки сортируемых колонок
                          // выходили строчными, а несортируемых — прописными.
                          // Рядом это читается как две разные таблицы;
                          // на «Материалах в отгрузках» так и было с самого
                          // начала, просто несортируемая колонка там одна.
                          "inline-flex items-center gap-1 rounded-sm uppercase transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
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
                onClick={clickable ? () => onToggle?.(row) : undefined}
                className={cn(
                  clickable && "cursor-pointer",
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
                      column.strong && "font-medium",
                      index === 0 && NAME_CELL,
                      changedCells.has(changedCellKey(key, column.key)) &&
                        "motion-data-flash"
                    )}
                  >
                    {index === 0 && expandable ? (
                      <span className="flex items-center gap-2">
                        <ChevronRight
                          aria-hidden
                          className={cn(
                            "motion-transform-transition size-3.5 shrink-0 text-muted-foreground",
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

              expandable && (open || key === collapsing) ? (
                <DetailRow
                  key={`${key}-detail`}
                  open={open}
                  colSpan={columns.length}
                  onCollapsed={() =>
                    setTracked((current) =>
                      current.collapsing === key
                        ? { ...current, collapsing: null }
                        : current
                    )
                  }
                >
                  {renderDetail?.(row)}
                </DetailRow>
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
                  className={cn(
                    column.numeric && "text-right tabular-nums",
                    // `whitespace-normal` обязателен: `TableCell` из реестра
                    // объявляет `whitespace-nowrap`, а ячейка имени —
                    // `max-w-0`. Вместе это значит, что подпись итога никуда
                    // не переносится и вытекает поверх соседней ячейки:
                    // «Итого · 212 материалов» наезжало на «разные единицы».
                    // У строк таблицы этого не видно только потому, что
                    // страницы сами оборачивают имя в обрезающий span.
                    index === 0 && cn(NAME_CELL, "whitespace-normal"),
                  )}
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
