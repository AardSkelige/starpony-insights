import * as React from "react"

import { exportUrl, useDeadlines } from "@/sections/deadlines/api"
import { COLUMNS, SORT_KEYS, totalsFor } from "@/sections/deadlines/columns"
import { Aging } from "@/sections/deadlines/ui/aging"
import { Coverage } from "@/sections/deadlines/ui/coverage"
import { Marketplaces } from "@/sections/deadlines/ui/marketplaces"
import { RowDetail } from "@/sections/deadlines/ui/row-detail"
import { refreshNote, useRefresh, useSyncStatus } from "@/shared/api/sync"
import { DataTable } from "@/shared/components/data-table"
import { DetailDrawer } from "@/shared/components/detail-drawer"
import { FiltersBar } from "@/shared/components/filters/bar"
import { Page } from "@/shared/components/page"
import { PageHeader } from "@/shared/components/page-header"
import { TableFooter } from "@/shared/components/table-footer"
import { useScreen } from "@/shared/hooks/use-screen"
import { useTableParams } from "@/shared/hooks/use-table-params"
import { withPlural } from "@/shared/lib/plural"

const SEARCH_PLACEHOLDER = "Название контрагента"
const SEARCH_LABEL = "Поиск по контрагентам"

/**
 * «Сроки оплаты»: кто должен, сколько и как давно.
 *
 * **Периода на странице нет.** У соседей он задаёт, что посчитано —
 * отгрузки августа, приёмки квартала. Здесь показано состояние на сегодня:
 * выбери человек «август», и долг возрастом 93 дня исчез бы с экрана,
 * то есть фильтр спрятал бы ровно то, ради чего страницу открывают.
 *
 * **Под таблицей три блока, и порядок у них не случайный.** Площадки —
 * открытым блоком, потому что это четверть отгруженного и прятать её нельзя.
 * «Где застряли деньги» — свёрнуто, отвечает на «есть ли повод беспокоиться».
 * «Вся картина расчётов» — свёрнуто, отвечает на «почему в таблице только
 * двое», и его открывают реже всего.
 */
export function DeadlinesPage() {
  const screen = useScreen()
  // Минус обязателен: «debt» значит «по возрастанию», и страница
  // открывалась бы с того, кто должен меньше всех.
  const table = useTableParams({
    defaultSort: "-debt",
    sortKeys: SORT_KEYS,
    // Справочника нет: контрагент и есть строка таблицы.
    // Периода тоже: долг — состояние на сегодня. Даты при этом не заводятся
    // в адресе и не считаются применённым фильтром — иначе ссылка вида
    // `?from=…`, оставшаяся от соседней страницы, дала бы пустое состояние
    // «попробуйте изменить фильтр» там, где менять нечего.
    period: false,
  })

  const refresh = useRefresh()
  // Прогон могли запустить в другой вкладке или вовсе не вы — кнопка обязана
  // это показывать, иначе четверо коллег нажмут её впустую.
  const sync = useSyncStatus()

  const query = useDeadlines({
    ...table.applied,
    page: table.page,
    ordering: table.ordering,
    pageSize: table.pageSize,
  })
  const data = query.data

  // Только идентификатор: снимок строки после «Обновить» показывал бы
  // старые числа рядом со свежим разбором.
  const [pickedId, setPickedId] = React.useState<number | null>(null)

  const rows = data?.results ?? []
  const picked = rows.find((row) => row.agent_id === pickedId) ?? null
  const pageCount = data ? Math.max(1, Math.ceil(data.count / table.pageSize)) : 1

  return (
    <Page>
      <PageHeader
        title="Сроки оплаты"
        subtitle="Кто должен, сколько и как давно"
        syncedAt={data?.synced_at ?? null}
        onRefresh={() => refresh.mutate()}
        refreshing={refresh.isPending || sync.running}
        refreshNote={refreshNote(refresh, sync.running, sync)}
        onExport={() => {
          window.location.assign(
            exportUrl({ search: table.applied.search, ordering: table.ordering })
          )
        }}
      />

      <FiltersBar
        value={table.filters}
        onChange={table.changeFilters}
        onReset={table.resetFilters}
        // Долг — состояние на сегодня, а не итог за отрезок.
        period={false}
        searchPlaceholder={SEARCH_PLACEHOLDER}
        searchLabel={SEARCH_LABEL}
      />

      <DataTable
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.agent_id}
        loading={query.isPending}
        // Приглушаются только устаревшие данные — те, что показаны, пока
        // едут новые после смены поиска или страницы.
        refreshing={query.isPlaceholderData}
        // Тот же признак, что у кнопки и отметки свежести: чужой прогон
        // виден всем, и его результат подсвечивается так же, как свой.
        syncPending={refresh.isPending || sync.running}
        syncFailed={refresh.isError}
        dataVersion={query.dataUpdatedAt}
        error={query.isError}
        onRetry={() => query.refetch()}
        emptyTitle={
          table.activeCount > 0
            ? "Под этот запрос должники не нашлись"
            : "Все расплатились"
        }
        emptyHint={
          table.activeCount > 0
            ? "Попробуйте изменить запрос."
            : "Неоплаченных документов в учёте нет. Данные берутся из МойСклада — появятся после первой синхронизации."
        }
        renderDetail={(row) => <RowDetail row={row} />}
        expandedKey={table.expanded}
        onToggle={(row) =>
          table.setExpanded((current) =>
            current === row.agent_id ? null : row.agent_id
          )
        }
        onOpen={(row) => setPickedId(row.agent_id)}
        totals={data ? totalsFor(data.totals) : undefined}
        sort={table.sort}
        onSort={table.changeSort}
      />

      {data && (rows.length > 0 || table.page > 1) ? (
        <TableFooter
          // Оба числа — про показанные строки. Документы из `coverage`
          // описывают всю картину, и при поиске подвал читался бы как
          // «1 контрагент · 189 документов».
          summary={`${withPlural(data.count, "контрагент", "контрагента", "контрагентов")} · ${withPlural(data.totals.documents_count, "документ", "документа", "документов")}`}
          page={table.page}
          pageCount={pageCount}
          pageSize={table.pageSize}
          onPage={table.setPage}
          onPageSize={table.setPageSize}
        />
      ) : null}

      {/* Площадки — открытым блоком: товар ушёл, деньги не пришли, прятать
          это нельзя. Но и в итог дебиторки они не входят: выплата приходит
          реестром и в учёт не заводится. */}
      {data ? <Marketplaces rows={data.marketplaces} /> : null}

      {/* Свёрнутые блоки — под таблицей, как на четырёх соседних страницах. */}
      {data ? <Aging aging={data.aging} /> : null}
      {data ? <Coverage coverage={data.coverage} /> : null}

      {/* Разбор — для узкого экрана и телефона. На широком он раскрывается
          прямо в строке.

          `inDrawer` отвечает за два следствия сразу: числа самой строки
          повторяются (строка закрыта затемнением, свериться с ней нельзя)
          и разбор не добавляет свой отступ — панель даёт собственный. */}
      {screen !== "wide" ? (
        <DetailDrawer
          open={picked !== null}
          title={picked?.name ?? ""}
          subtitle={
            picked
              ? `${withPlural(picked.documents_count, "документ", "документа", "документов")} · старейшему ${withPlural(picked.oldest_age_days, "день", "дня", "дней")}`
              : undefined
          }
          onClose={() => setPickedId(null)}
        >
          {picked ? <RowDetail row={picked} inDrawer /> : null}
        </DetailDrawer>
      ) : null}
    </Page>
  )
}
