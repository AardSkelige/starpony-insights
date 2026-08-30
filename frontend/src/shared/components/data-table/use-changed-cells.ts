import * as React from "react"

import type { Column } from "@/shared/components/data-table/columns"
import {
  findChangedCells,
  type RowKey,
} from "@/shared/components/data-table/changes"

const EMPTY = new Set<string>()

/**
 * Снимок делается только на фронте синхронизации с МойСкладом.
 *
 * **Чужой прогон подсвечивается наравне со своим.** Кнопка и отметка свежести
 * показывают его всем, кто сейчас на странице (`useSyncStatus`), — и обещание,
 * данное этим показом, обязано закрыться тем же ответом. Иначе четверо из пяти
 * видят «идёт обновление», дожидаются его и не понимают, что изменилось.
 *
 * `selectionChanging` — отдельный предохранитель: тот же запрос таблицы
 * запускают фильтр, сортировка и пагинация, но подсветка после них означала
 * бы совсем другое и быстро превратила бы сигнал в шум.
 */
export function useChangedCells<Row>({
  columns,
  rows,
  rowKey,
  syncPending,
  syncFailed,
  dataVersion,
  selectionChanging,
}: {
  columns: Column<Row>[]
  rows: Row[]
  rowKey: (row: Row) => RowKey
  /** Прогон идёт — свой или запущенный кем-то ещё. */
  syncPending: boolean
  /** Прогон не состоялся: отказ по лимиту или ошибка. Сравнивать нечего. */
  syncFailed: boolean
  dataVersion: number
  selectionChanging: boolean
}): Set<string> {
  const [changed, setChanged] = React.useState<{
    dataVersion: number
    cells: Set<string>
  }>(() => ({ dataVersion: 0, cells: EMPTY }))
  const wasPending = React.useRef(false)
  const snapshot = React.useRef<{ rows: Row[]; dataVersion: number } | null>(
    null
  )

  React.useEffect(() => {
    if (syncPending && !wasPending.current) {
      snapshot.current = { rows: [...rows], dataVersion }
    }
    wasPending.current = syncPending
  }, [dataVersion, syncPending, rows])

  React.useEffect(() => {
    if (selectionChanging) {
      snapshot.current = null
    }
  }, [selectionChanging])

  React.useEffect(() => {
    const before = snapshot.current
    if (syncPending || !before) return

    if (syncFailed) {
      snapshot.current = null
      return
    }

    // Прогон заканчивается раньше, чем таблица успевает перечитаться.
    // Сравнивать старые строки с ними же нельзя: ждём нового ответа запроса.
    if (dataVersion <= before.dataVersion) return

    snapshot.current = null
    setChanged({
      dataVersion,
      cells: findChangedCells({
        before: before.rows,
        after: rows,
        columns,
        rowKey,
      }),
    })
  }, [
    columns,
    dataVersion,
    rowKey,
    rows,
    syncFailed,
    syncPending,
  ])

  // Новый запрос (включая смену выборки и фоновое перечитывание) не должен
  // повторно показывать результат прошлого прогона.
  if (
    syncPending ||
    selectionChanging ||
    changed.dataVersion !== dataVersion
  ) {
    return EMPTY
  }
  return changed.cells
}
