import * as React from "react"
import { parseAsInteger, parseAsString, useQueryStates } from "nuqs"

import { exportUrl, useShipmentProducts } from "@/sections/shipments-products/api"
import { COLUMNS } from "@/sections/shipments-products/columns"
import { DetailPanel } from "@/sections/shipments-products/ui/detail-panel"
import { Filters, type FilterValue } from "@/sections/shipments-products/ui/filters"
import { FiltersDrawer } from "@/sections/shipments-products/ui/filters-drawer"
import { RowDetail } from "@/sections/shipments-products/ui/row-detail"
import {
  DataTable,
  DEFAULT_PAGE_SIZE,
  PAGE_SIZES,
  type Sort,
  type Totals,
} from "@/shared/components/data-table"
import { Page, Toolbar } from "@/shared/components/page"
import { PageHeader } from "@/shared/components/page-header"
import { PageSize } from "@/shared/components/page-size"
import { refusalText, useRefresh, useSyncStatus } from "@/shared/api/sync"
import { TablePagination } from "@/shared/components/table-pagination"
import { useDebounced } from "@/shared/hooks/use-debounced"
import { useScreen } from "@/shared/hooks/use-screen"
import { formatMoney, formatQuantity } from "@/shared/lib/format"

/**
 * Фильтры живут в адресной строке, а не в состоянии компонента.
 *
 * Так ссылку на «репеллент за июнь по Озону» можно переслать, а «назад»
 * в браузере возвращает к прежней выборке, а не выбрасывает со страницы.
 */
const FILTER_PARSERS = {
  from: parseAsString,
  to: parseAsString,
  channel: parseAsInteger,
  q: parseAsString.withDefault(""),
  page: parseAsInteger.withDefault(1),
  // Сортировка и высота страницы тоже в адресной строке: пересланная ссылка
  // должна открыться ровно тем, что человек видел, когда её копировал.
  // Минус обязателен: «revenue» — это по возрастанию, и страница
  // открывалась бы с позиций, не принесших ничего.
  sort: parseAsString.withDefault("-revenue"),
  size: parseAsInteger.withDefault(DEFAULT_PAGE_SIZE),
}

export function ShipmentProductsPage() {
  const screen = useScreen()
  const [params, setParams] = useQueryStates(FILTER_PARSERS)

  const filters: FilterValue = {
    dateFrom: params.from,
    dateTo: params.to,
    channelId: params.channel,
    search: params.q,
  }

  // В запрос уходит осевшее значение поиска, в поле — набранное. Иначе
  // каждая буква поднимает три поиска по подстроке, подсчёт строк и итоги
  // по всей выборке: слово из девяти букв — девять таких запросов.
  const settledSearch = useDebounced(params.q)
  const applied = { ...filters, search: settledSearch }

  // Размер страницы из адреса может быть любым — берём только известный,
  // иначе ссылка с `size=100000` уводит базу в долгий скан.
  const pageSize = (PAGE_SIZES as readonly number[]).includes(params.size)
    ? params.size
    : DEFAULT_PAGE_SIZE

  const refresh = useRefresh()
  // Прогон могли запустить в другой вкладке или вовсе не вы — кнопка обязана
  // это показывать, иначе четверо коллег нажмут её впустую.
  const sync = useSyncStatus()

  const query = useShipmentProducts({
    ...applied,
    page: params.page,
    ordering: params.sort,
    pageSize,
  })
  const data = query.data

  // Раскрытая строка — на широком экране; выбранная для панели — на остальных.
  const [expanded, setExpanded] = React.useState<number | null>(null)
  // Только идентификатор: снимок строки после «Обновить» показывал бы
  // старые числа рядом со свежей разбивкой по каналам.
  const [pickedId, setPickedId] = React.useState<number | null>(null)

  const changeFilters = React.useCallback(
    (patch: Partial<FilterValue>) => {
      // Любая смена фильтра возвращает на первую страницу: остаться на пятой
      // в выборке, где всего две, — это пустой экран без объяснения.
      setParams({
        ...(patch.dateFrom !== undefined ? { from: patch.dateFrom } : {}),
        ...(patch.dateTo !== undefined ? { to: patch.dateTo } : {}),
        ...(patch.channelId !== undefined ? { channel: patch.channelId } : {}),
        ...(patch.search !== undefined ? { q: patch.search } : {}),
        page: 1,
      })
      setExpanded(null)
    },
    [setParams]
  )

  const resetFilters = React.useCallback(() => {
    setParams({ from: null, to: null, channel: null, q: "", page: 1 })
    setExpanded(null)
  }, [setParams])

  // Минус — убывание, как понимает бэкенд и как принято в SQL.
  const sort: Sort = {
    key: params.sort.replace(/^-/, ""),
    desc: params.sort.startsWith("-"),
  }

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

  const activeCount = [
    filters.dateFrom || filters.dateTo,
    filters.channelId,
    filters.search,
  ].filter(Boolean).length

  const rows = data?.results ?? []
  const pageCount = data ? Math.max(1, Math.ceil(data.count / pageSize)) : 1

  return (
    <Page>
      <PageHeader
        title="Товары в отгрузках"
        subtitle="Что и сколько продано за период"
        syncedAt={data?.synced_at ?? null}
        onRefresh={() => refresh.mutate()}
        refreshing={refresh.isPending || sync.running}
        refreshNote={refreshNote(refresh, sync.running)}
        onExport={() => {
          window.location.assign(exportUrl({ ...applied, ordering: params.sort }))
        }}
      />

      <Toolbar>
        <Filters
          value={filters}
          onChange={changeFilters}
          onReset={resetFilters}
          channels={data?.channels ?? []}
        />
      </Toolbar>

      <FiltersDrawer
        value={filters}
        onChange={changeFilters}
        onReset={resetFilters}
        channels={data?.channels ?? []}
        activeCount={activeCount}
      />

      <DataTable
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.product_id}
        loading={query.isPending}
        // Приглушаются только устаревшие данные — те, что показаны, пока
        // едут новые после смены фильтра или страницы. Любая загрузка
        // подряд не годится: React Query перечитывает данные при возврате
        // на вкладку, и таблица темнела каждый раз, когда человек
        // переключался в другое окно и обратно, хотя числа не менялись.
        refreshing={query.isPlaceholderData}
        error={query.isError}
        onRetry={() => query.refetch()}
        emptyTitle="За этот период ничего не продано"
        emptyHint={
          activeCount > 0
            ? "Попробуйте расширить период или снять фильтр по каналу."
            : "Данные появятся после первой синхронизации с МойСкладом."
        }
        renderDetail={(row) => <RowDetail row={row} query={applied} />}
        expandedKey={expanded}
        onToggle={(row) =>
          setExpanded((current) => (current === row.product_id ? null : row.product_id))
        }
        onOpen={(row) => setPickedId(row.product_id)}
        totals={data ? totalsFor(data.totals) : undefined}
        sort={sort}
        onSort={changeSort}
      />

      {data && (rows.length > 0 || params.page > 1) ? (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {data.count} наименований · {data.totals.documents_count} отгрузок
          </span>
          <PageSize
            value={pageSize}
            onChange={(size) => setParams({ size, page: 1 })}
          />
          <div className="ml-auto">
            <TablePagination
              page={params.page}
              pageCount={pageCount}
              onChange={(next) => setParams({ page: next })}
            />
          </div>
        </div>
      ) : null}

      {/* Панель деталей — для узкого экрана и телефона. На широком те же
          детали раскрываются прямо в строке. */}
      {screen !== "wide" ? (
        <DetailPanel
          row={rows.find((row) => row.product_id === pickedId) ?? null}
          query={applied}
          onClose={() => setPickedId(null)}
        />
      ) : null}
    </Page>
  )
}

/**
 * Что сказать про последнее нажатие «Обновить».
 *
 * Прогон почти всегда заканчивается теми же числами на экране, поэтому без
 * явного ответа кнопка выглядит сломанной. Отказ приходит с сервера уже
 * написанным для человека — здесь его не переписывают.
 */
function refreshNote(
  refresh: ReturnType<typeof useRefresh>,
  running: boolean
): string | null {
  // `running` покрывает и чужой прогон, и свой после перезагрузки страницы,
  // когда состояние мутации уже потеряно.
  if (refresh.isPending || running) return "идёт обновление из МойСклада…"

  const refusal = refusalText(refresh.error)
  if (refusal) return refusal

  if (refresh.isError) return "обновить не удалось"

  if (refresh.isSuccess) {
    const run = refresh.data
    // Прогон отвечает двухсотым и когда часть сущностей не доехала:
    // предохранитель мог остановить его после двух справочников из семи.
    // Сказать «обновлено» в этом случае — соврать ровно там, где человек
    // решает, доверять ли числам на экране.
    if (run.status !== "success") {
      return `${run.status_label.toLowerCase()} — часть данных могла не обновиться`
    }
    const seconds = run.duration_seconds
    return seconds ? `обновлено за ${seconds.toFixed(0)} с` : "обновлено"
  }

  return null
}

/**
 * Итог по всей выборке, а не по видимой странице.
 *
 * Задаётся ключами колонок: подвал, собранный из шести ячеек подряд,
 * разъехался бы с таблицей на первой же колонке, скрытой на узком экране.
 *
 * Средней цены в итоге нет намеренно: среднее по разным товарам — число,
 * которое ничего не значит. Прочерк честнее.
 */
function totalsFor(
  totals: NonNullable<ReturnType<typeof useShipmentProducts>["data"]>["totals"]
): Totals {
  return {
    label: `Итого за период · ${totals.products_count} наименований`,
    values: {
      quantity: formatQuantity(totals.quantity),
      free: formatQuantity(totals.free_quantity),
      revenue: formatMoney(totals.revenue_kopecks),
      avg: <span className="text-muted-foreground">—</span>,
      // Не строка «100 %»: когда выручка выборки нулевая, доли строк
      // приходят пустыми, и подвал заявлял бы сто процентов над колонкой
      // из прочерков.
      share:
        totals.revenue_kopecks > 0 ? (
          "100 %"
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
  }
}
