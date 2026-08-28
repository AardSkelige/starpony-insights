import type { SalesChannel } from "@/shared/api/types"
import { Filters, type FilterValue } from "@/shared/components/filters"
import { Toolbar } from "@/shared/components/page"

/**
 * Фильтры страницы — один блок на все три ширины экрана.
 *
 * Раньше видов было два: ряд на широком экране и кнопка с выдвижной панелью
 * на телефоне. Панель убрана — на телефоне поля стоят столбиком прямо
 * на странице. Причина не в вёрстке: чтобы найти позицию, приходилось нажать
 * «Фильтры», дождаться панели, ввести запрос и закрыть её — четыре действия
 * там, где ожидается одно, и всё это ради экрана, на который приходят
 * именно искать.
 *
 * Обёртка остаётся, хотя внутри теперь одна строка: страницы обращаются
 * к фильтрам через неё, и вернись когда-нибудь второй вид, менять придётся
 * это место, а не каждую из десяти страниц.
 */
export function FiltersBar(props: {
  value: FilterValue
  onChange: (patch: Partial<FilterValue>) => void
  onReset: () => void
  channels: SalesChannel[]
  /** Что ищут на этой странице — подсказка в поле и подпись для чтения с экрана. */
  searchPlaceholder: string
  searchLabel: string
}) {
  return (
    <Toolbar>
      <Filters {...props} />
    </Toolbar>
  )
}
