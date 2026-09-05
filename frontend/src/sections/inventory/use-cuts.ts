import * as React from "react"
import { parseAsString, useQueryStates } from "nuqs"

import type { InventoryCuts } from "@/sections/inventory/api"

/**
 * Склад и папка — в адресной строке, как и остальные фильтры.
 *
 * Отдельным хуком, а не `picker` в `useTableParams`: тот кладёт в запрос
 * идентификатор справочника, а склада как сущности у нас нет — он приходит
 * именем внутри инвентаризации. Двух справочников `picker` тоже не знает,
 * а здесь их два, и оба сужают выборку по-разному: склад — пересчёты,
 * папка — саму номенклатуру.
 *
 * **Смена любого возвращает на первую страницу.** Оставшись на пятой
 * в выборке, где строк стало меньше, человек получил бы пустой экран
 * без объяснения.
 */
export function useInventoryCuts(onChange: () => void) {
  const [params, setParams] = useQueryStates({
    store: parseAsString.withDefault(""),
    folder: parseAsString.withDefault(""),
  })

  const cuts: InventoryCuts = { store: params.store, folder: params.folder }

  const setCuts = React.useCallback(
    (patch: Partial<InventoryCuts>) => {
      setParams(patch)
      onChange()
    },
    [setParams, onChange]
  )

  const reset = React.useCallback(() => {
    setParams({ store: "", folder: "" })
    onChange()
  }, [setParams, onChange])

  return { cuts, setCuts, reset, activeCount: Number(!!params.store) + Number(!!params.folder) }
}
