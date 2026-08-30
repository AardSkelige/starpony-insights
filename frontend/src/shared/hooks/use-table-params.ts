import * as React from "react"
import { parseAsInteger, parseAsString, useQueryStates } from "nuqs"

import {
  DEFAULT_PAGE_SIZE,
  PAGE_SIZES,
  type Sort,
} from "@/shared/components/data-table/columns"
import type { FilterValue } from "@/shared/components/filters"
import { useDebounced } from "@/shared/hooks/use-debounced"

/**
 * Состояние страницы с таблицей: фильтры, сортировка, страница, высота.
 *
 * **Всё живёт в адресной строке, а не в состоянии компонента.** Так ссылку
 * на «сырьё за июнь по Озону» можно переслать, а «назад» в браузере
 * возвращает к прежней выборке, а не выбрасывает со страницы.
 *
 * В `shared/`, потому что у всех разделов это устроено одинаково — и должно
 * оставаться одинаковым: если на одной странице «назад» возвращает фильтры,
 * а на другой нет, человек перестаёт им пользоваться везде.
 */
export function useTableParams({
  defaultSort,
  sortKeys,
  pickerKey,
}: {
  defaultSort: string
  /**
   * Ключи сортировки, которые понимает этот раздел.
   *
   * Сортировка уходит в запрос как есть, а сервер принимает закрытый список
   * и отвечает 400 на всё остальное. Без проверки ссылка, скопированная
   * с соседней страницы, открывает не таблицу, а экран ошибки: у «Товаров»
   * порядок `-revenue`, у «Материалов» такого ключа нет вовсе.
   */
  sortKeys: readonly string[]
  /**
   * Имя справочника этой страницы: `channel` у отгрузок, `supplier`
   * у приёмок. В адрес уходит как есть, в запрос — с `_id`.
   *
   * Общего имени у них нет намеренно. Назови мы параметр `pick`, и ссылка
   * «pick=3» со страницы отгрузок открыла бы на приёмках поставщика номер
   * три — фильтр, выглядящий выбранным, но означающий не то.
   *
   * **Необязателен.** У «Поставщиков» справочника нет: поставщик там и есть
   * строка таблицы. Тогда в адрес не попадает ни параметра, ни его следа.
   */
  pickerKey?: string
}) {
  const [params, setParams] = useQueryStates({
    from: parseAsString,
    to: parseAsString,
    ...(pickerKey ? { [pickerKey]: parseAsInteger } : {}),
    q: parseAsString.withDefault(""),
    page: parseAsInteger.withDefault(1),
    // Минус обязателен: без него «revenue» значит «по возрастанию», и страница
    // открывалась бы с позиций, не принесших ничего.
    sort: parseAsString.withDefault(defaultSort),
    size: parseAsInteger.withDefault(DEFAULT_PAGE_SIZE),
  })

  const filters: FilterValue = {
    dateFrom: params.from,
    dateTo: params.to,
    // Приведение неизбежно: набор ключей теперь зависит от того, есть ли
    // у страницы справочник, а `useQueryStates` выводит их статически
    // и про условный ключ ничего не знает.
    pickId: pickerKey
      ? ((params as unknown as Record<string, number | null>)[pickerKey] ?? null)
      : null,
    search: params.q,
  }

  // В запрос уходит осевшее значение поиска, в поле — набранное. Иначе
  // каждая буква поднимает полный расчёт по всей выборке: слово из девяти
  // букв — девять таких запросов.
  const settledSearch = useDebounced(params.q)

  // Размер страницы из адреса может быть любым — берём только известный,
  // иначе ссылка с `size=100000` уводит базу в долгий скан.
  const pageSize = (PAGE_SIZES as readonly number[]).includes(params.size)
    ? params.size
    : DEFAULT_PAGE_SIZE

  // Порядок — то же самое: неизвестный ключ откатывается к своему, а не
  // уезжает в запрос, чтобы вернуться четырёхсотой.
  const ordering = sortKeys.includes(params.sort.replace(/^-/, ""))
    ? params.sort
    : defaultSort

  /**
   * Раскрытая строка сбрасывается при любой смене выборки.
   *
   * Иначе после смены фильтра раскрытой остаётся строка, которой в новой
   * выборке нет, — и под ней висит разбор, не относящийся ни к чему на экране.
   */
  const [expanded, setExpanded] = React.useState<number | null>(null)

  const changeFilters = React.useCallback(
    (patch: Partial<FilterValue>) => {
      // Любая смена фильтра возвращает на первую страницу: остаться на пятой
      // в выборке, где всего две, — это пустой экран без объяснения.
      setParams({
        ...(patch.dateFrom !== undefined ? { from: patch.dateFrom } : {}),
        ...(patch.dateTo !== undefined ? { to: patch.dateTo } : {}),
        ...(pickerKey && patch.pickId !== undefined
          ? { [pickerKey]: patch.pickId }
          : {}),
        ...(patch.search !== undefined ? { q: patch.search } : {}),
        page: 1,
      })
      setExpanded(null)
    },
    [setParams, pickerKey]
  )

  const resetFilters = React.useCallback(() => {
    setParams({
      from: null,
      to: null,
      ...(pickerKey ? { [pickerKey]: null } : {}),
      q: "",
      page: 1,
    })
    setExpanded(null)
  }, [setParams, pickerKey])

  const changeSort = React.useCallback(
    (key: string, numeric: boolean) => {
      setParams((current) => {
        const active = current.sort.replace(/^-/, "") === key
        // Повторный щелчок переворачивает порядок. Первый щелчок по новой
        // колонке зависит от того, что в ней: у денег и количеств интересен
        // верх списка, у названий — алфавит.
        const next = active
          ? current.sort.startsWith("-")
            ? key
            : `-${key}`
          : numeric
            ? `-${key}`
            : key
        return { sort: next, page: 1 }
      })
      setExpanded(null)
    },
    [setParams]
  )

  return {
    /** Что показывать в полях фильтров — набранное, без задержки. */
    filters,
    /**
     * Что отправлять в запрос — с осевшим поиском и с именем параметра,
     * которое понимает сервер: `channel_id` на отгрузках, `supplier_id`
     * на приёмках.
     */
    applied: {
      ...filters,
      search: settledSearch,
      // Без справочника имени параметра нет вовсе: пустая строка уехала бы
      // в адрес как `?_id=`, стоило бы `pickId` однажды оказаться не пустым.
      ...(pickerKey ? { pickParam: `${pickerKey}_id` } : {}),
    },
    /** Как сейчас отсортировано. Минус — убывание, как в SQL. */
    sort: {
      key: ordering.replace(/^-/, ""),
      desc: ordering.startsWith("-"),
    } satisfies Sort,
    ordering,
    page: params.page,
    pageSize,
    /** Сколько фильтров применено — число на кнопке «Фильтры» на телефоне. */
    activeCount: [
      filters.dateFrom || filters.dateTo,
      filters.pickId,
      filters.search,
    ].filter(Boolean).length,

    expanded,
    setExpanded,

    changeFilters,
    resetFilters,
    changeSort,
    setPage: (page: number) => setParams({ page }),
    setPageSize: (size: number) => setParams({ size, page: 1 }),
  }
}
