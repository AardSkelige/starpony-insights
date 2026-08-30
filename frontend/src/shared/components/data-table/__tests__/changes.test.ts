import { describe, expect, it } from "vitest"

import {
  changedCellKey,
  findChangedCells,
} from "@/shared/components/data-table/changes"
import type { Column } from "@/shared/components/data-table/columns"

type Row = { id: number; name: string; amount: number }

const columns: Column<Row>[] = [
  {
    key: "name",
    label: "Название",
    render: (row) => row.name,
    changeValue: (row) => row.name,
  },
  {
    key: "amount",
    label: "Сумма",
    render: (row) => row.amount,
    changeValue: (row) => row.amount,
  },
]

const rowKey = (row: Row) => row.id

function changes(before: Row[], after: Row[]) {
  return findChangedCells({ before, after, columns, rowKey })
}

describe("findChangedCells", () => {
  it("возвращает только действительно изменившуюся ячейку", () => {
    const result = changes(
      [{ id: 1, name: "Глина", amount: 10 }],
      [{ id: 1, name: "Глина", amount: 12 }]
    )

    expect(result).toEqual(new Set([changedCellKey(1, "amount")]))
  })

  it("ничего не возвращает для тех же значений", () => {
    const rows = [{ id: 1, name: "Глина", amount: 10 }]
    expect(changes(rows, [{ ...rows[0] }])).toEqual(new Set())
  })

  it("считает все ячейки новой строки изменившимися", () => {
    const result = changes(
      [{ id: 1, name: "Глина", amount: 10 }],
      [
        { id: 1, name: "Глина", amount: 10 },
        { id: 2, name: "Воск", amount: 5 },
      ]
    )

    expect(result).toEqual(
      new Set([changedCellKey(2, "name"), changedCellKey(2, "amount")])
    )
  })

  it("не пытается подсветить исчезнувшую строку", () => {
    const result = changes(
      [
        { id: 1, name: "Глина", amount: 10 },
        { id: 2, name: "Воск", amount: 5 },
      ],
      [{ id: 1, name: "Глина", amount: 10 }]
    )

    expect(result).toEqual(new Set())
  })

  it("гасит сигнал, когда множество строк сменилось целиком", () => {
    const result = changes(
      [{ id: 1, name: "Глина", amount: 10 }],
      [{ id: 2, name: "Воск", amount: 5 }]
    )

    expect(result).toEqual(new Set())
  })
})
