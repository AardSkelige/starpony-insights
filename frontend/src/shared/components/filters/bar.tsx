import type { SalesChannel } from "@/shared/api/types"
import { Filters, type FilterValue } from "@/shared/components/filters"
import { FiltersDrawer } from "@/shared/components/filters/drawer"
import { Toolbar } from "@/shared/components/page"

/**
 * Фильтры страницы в обоих видах сразу: ряд на широком экране и кнопка
 * с выдвижной панелью на телефоне.
 *
 * Одним компонентом, потому что виды показывают **одно и то же** — разными
 * средствами. Пока их было два, страница передавала один и тот же набор
 * дважды, и добавление фильтра требовало не забыть про вторую половину.
 * Забыть про неё легко: на широком экране кнопки не видно вовсе.
 */
export function FiltersBar({
  activeCount,
  ...shared
}: {
  value: FilterValue
  onChange: (patch: Partial<FilterValue>) => void
  onReset: () => void
  channels: SalesChannel[]
  /** Что ищут на этой странице — подсказка в поле и подпись для чтения с экрана. */
  searchPlaceholder: string
  searchLabel: string
  /** Сколько фильтров применено — число на кнопке «Фильтры» на телефоне. */
  activeCount: number
}) {
  return (
    <>
      <Toolbar>
        <Filters {...shared} />
      </Toolbar>
      <FiltersDrawer {...shared} activeCount={activeCount} />
    </>
  )
}
