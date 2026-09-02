import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { TableView } from "@/shared/components/data-table/table-view"
import type { Column } from "@/shared/components/data-table/columns"

/**
 * Строка обязана открываться щелчком **и там, где разбора внутри таблицы нет**.
 *
 * Дефект, ради которого написан этот файл, жил в общем компоненте и убивал
 * разбор на **всех** страницах сразу — но только на средней ширине. Причина:
 * щелчок вешался по условию `Boolean(renderDetail)`, а на узком экране
 * `renderDetail` не передаётся вовсе — разбор там показывается выдвижной
 * панелью. Строка оставалась мёртвой: ни обработчика, ни курсора, ни ошибки
 * в консоли. Нашлось снимками на 900 точках, через неделю после того,
 * как первая страница была сдана.
 *
 * Проверяется рендером: условие живёт в разметке, и опечатка в нём вернула бы
 * прежнее поведение молча.
 */
type Row = { id: number; name: string }

const COLUMNS: Column<Row>[] = [
  { key: "name", label: "Имя", changeValue: (row) => row.name, render: (row) => row.name },
]

const ROWS: Row[] = [{ id: 1, name: "КРМОО «Каприоль»" }]

function renderTable(props: Partial<Parameters<typeof TableView<Row>>[0]> = {}) {
  return render(
    <TableView
      columns={COLUMNS}
      rows={ROWS}
      rowKey={(row) => row.id}
      {...props}
    />
  )
}

describe("щелчок по строке таблицы", () => {
  it("работает без разбора внутри таблицы — им открывается панель", () => {
    const onToggle = vi.fn()
    renderTable({ onToggle })

    fireEvent.click(screen.getByText("КРМОО «Каприоль»"))

    expect(onToggle).toHaveBeenCalledWith(ROWS[0])
  })

  it("работает и с разбором внутри таблицы — там он раскрывается на месте", () => {
    const onToggle = vi.fn()
    renderTable({ onToggle, renderDetail: () => <div>разбор</div> })

    fireEvent.click(screen.getByText("КРМОО «Каприоль»"))

    expect(onToggle).toHaveBeenCalledWith(ROWS[0])
  })

  it("строка без обработчика остаётся обычной", () => {
    // Курсор-указатель обещает, что по строке можно нажать. Обещание без
    // обработчика хуже его отсутствия: человек жмёт и не получает ничего.
    const { container } = renderTable()
    const row = container.querySelector("tbody tr")

    expect(row?.className).not.toContain("cursor-pointer")
  })
})
