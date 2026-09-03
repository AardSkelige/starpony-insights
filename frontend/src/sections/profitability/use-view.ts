import * as React from "react"
import { parseAsBoolean, parseAsStringLiteral, useQueryStates } from "nuqs"

import type { Basis, ProfitabilityView } from "@/sections/profitability/api"

const BASES = ["sold", "shipped"] as const

/**
 * База расчёта и подарки — в адресной строке, как и остальные фильтры.
 *
 * Отдельным хуком, а не полем в `useTableParams`: у остальных девяти страниц
 * такого выбора нет. Ссылку при этом можно переслать — и она откроется тем
 * же, что человек видел, включая базу.
 *
 * **Смена любого из двух возвращает на первую страницу.** Оставшись на пятой
 * в выборке, где строк стало меньше, человек получил бы пустой экран без
 * объяснения — тот же довод, что у смены фильтра.
 */
export function useProfitabilityView(onChange: () => void) {
  const [params, setParams] = useQueryStates({
    basis: parseAsStringLiteral(BASES).withDefault("sold"),
    // «Без подарков» — умолчание: у подарка есть себестоимость и нет выручки,
    // и включённым он тянет маржу вниз у каждого четвёртого товара.
    free: parseAsBoolean.withDefault(false),
  })

  const view: ProfitabilityView = { basis: params.basis, withFree: params.free }

  const setBasis = React.useCallback(
    (basis: Basis) => {
      setParams({ basis })
      onChange()
    },
    [setParams, onChange]
  )

  const setWithFree = React.useCallback(
    (free: boolean) => {
      setParams({ free })
      onChange()
    },
    [setParams, onChange]
  )

  return { view, setBasis, setWithFree }
}
