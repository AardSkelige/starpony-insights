import type { Column } from "@/shared/components/data-table/columns"

export type RowKey = string | number

/** Один ключ годится и для таблицы, и для карточек на телефоне. */
export function changedCellKey(rowKey: RowKey, columnKey: string): string {
  return JSON.stringify([rowKey, columnKey])
}

/**
 * Какие видимые ячейки изменились между снимками одной выборки.
 *
 * Новая строка целиком считается изменившейся. Исчезнувшая не даёт ключей:
 * подсвечивать в новом кадре уже нечего. Если множества строк не пересекаются
 * вовсе, это другая выборка, а не результат синхронизации — сигнал гасится.
 */
export function findChangedCells<Row>({
  before,
  after,
  columns,
  rowKey,
}: {
  before: Row[]
  after: Row[]
  columns: Column<Row>[]
  rowKey: (row: Row) => RowKey
}): Set<string> {
  const previous = new Map(before.map((row) => [rowKey(row), row]))
  const currentKeys = new Set(after.map(rowKey))
  const overlaps = [...previous.keys()].some((key) => currentKeys.has(key))

  if (before.length > 0 && after.length > 0 && !overlaps) return new Set()

  const changed = new Set<string>()
  for (const row of after) {
    const key = rowKey(row)
    const oldRow = previous.get(key)

    for (const column of columns) {
      if (
        !oldRow ||
        !sameValue(column.changeValue(oldRow), column.changeValue(row))
      ) {
        changed.add(changedCellKey(key, column.key))
      }
    }
  }

  return changed
}

/** Ответы API состоят из JSON-значений; так сравниваются и составные ячейки. */
function sameValue(left: unknown, right: unknown): boolean {
  return (
    Object.is(left, right) || JSON.stringify(left) === JSON.stringify(right)
  )
}
