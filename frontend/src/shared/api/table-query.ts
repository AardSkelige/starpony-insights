/**
 * Запрос таблицы раздела: период, канал, поиск, страница, порядок.
 *
 * У всех разделов он одинаков — и должен оставаться таким. Копия на каждый
 * раздел уже была, и обе сборки адреса совпадали слово в слово: тридцать
 * строк, повторённых дважды, из которых любая правка (новый фильтр, другое
 * имя параметра) обязана быть внесена в оба места, а вносится в одно.
 *
 * Всё это живёт в адресной строке страницы, поэтому ссылку на «сырьё
 * за июнь по Озону» можно переслать, и она откроется тем же.
 */
export type TableQuery = {
  dateFrom: string | null
  dateTo: string | null
  channelId: number | null
  search: string
  page: number
  ordering?: string
  pageSize?: number
}

/**
 * Та же выборка без страницы.
 *
 * Детали строки и выгрузка описывают **всю** отобранную выборку, а не ту
 * сотню строк, что видно на экране: разбор обязан сходиться с числом своей
 * строки, а файл — содержать отобранное целиком.
 */
export type TableSelection = Omit<TableQuery, "page">

/**
 * Параметры запроса. Умолчания не пишутся: адрес должен говорить только
 * о том, что человек выбрал, — иначе `?page=1&search=` появляется в каждой
 * пересылаемой ссылке и мешает читать, что в ней важного.
 */
function toSearchParams(query: TableQuery): string {
  const params = new URLSearchParams()
  if (query.dateFrom) params.set("date_from", query.dateFrom)
  if (query.dateTo) params.set("date_to", query.dateTo)
  if (query.channelId) params.set("channel_id", String(query.channelId))
  if (query.search) params.set("search", query.search)
  if (query.page > 1) params.set("page", String(query.page))
  if (query.ordering) params.set("ordering", query.ordering)
  if (query.pageSize) params.set("page_size", String(query.pageSize))
  return params.toString()
}

/** Адрес запроса вместе с выборкой: «/api/shipments/products/?date_from=…». */
export function withQuery(path: string, query: TableQuery): string {
  const params = toSearchParams(query)
  return params ? `${path}?${params}` : path
}

/** Адрес для запроса, которому страница не нужна: детали строки, выгрузка. */
export function withSelection(path: string, selection: TableSelection): string {
  return withQuery(path, { ...selection, page: 1 })
}
