import * as React from "react"

import { exportUrl, useProfitability } from "@/sections/profitability/api"
import { COLUMNS, SORT_KEYS, totalsFor } from "@/sections/profitability/columns"
import { useProfitabilityView } from "@/sections/profitability/use-view"
import { Coverage } from "@/sections/profitability/ui/coverage"
import { Families } from "@/sections/profitability/ui/families"
import { FreeAndLosses } from "@/sections/profitability/ui/free-and-losses"
import { Marketplaces } from "@/sections/profitability/ui/marketplaces"
import { maxProfit, ProfitScaleContext } from "@/sections/profitability/ui/profit-scale"
import { RowDetail } from "@/sections/profitability/ui/row-detail"
import { Summary } from "@/sections/profitability/ui/summary"
import { ViewToggle } from "@/sections/profitability/ui/view-toggle"
import { WarningStrip } from "@/sections/profitability/ui/warning-strip"
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

const SEARCH_PLACEHOLDER = "Название или артикул"
const SEARCH_LABEL = "Поиск по товарам"

/**
 * «Прибыльность»: на чём зарабатываем и на чём теряем.
 *
 * **Оговорка про площадки стоит выше таблицы.** Это единственное место
 * на странице, где предупреждение не свёрнуто: маржа Озона в 90,5 % —
 * число до комиссии, и прочитать его как факт нельзя. Всё остальное живёт
 * под таблицей свёрнутыми блоками, как на пяти соседних страницах.
 *
 * **Пять блоков, по одному на вопрос.** Итог за период, площадки, подарки
 * с убытками, линейки и полнота расчёта. Заголовок каждого несёт главное
 * число — свёрнутый блок обязан оставаться осмысленным (`DESIGN.md` §7).
 *
 * **Справочника в фильтрах нет.** Канал продаж в зеркале отчёта прибыльности
 * не хранится: разбивка по девяти каналам стоила бы девяти лишних запросов
 * к МойСкладу каждую ночь из корзины, общей с ботом. Разрез по каналам живёт
 * на своей странице.
 */
export function ProfitabilityPage() {
  const screen = useScreen()
  // Минус обязателен: «profit» значит «по возрастанию», и страница
  // открывалась бы с товара, принёсшего меньше всех.
  const table = useTableParams({
    defaultSort: "-profit",
    sortKeys: SORT_KEYS,
  })

  // Смена базы или подарков возвращает на первую страницу и закрывает
  // разбор: строки после неё другие, и раскрытой осталась бы та, которой
  // в новой выборке может не быть.
  const resetPosition = React.useCallback(() => {
    table.setPage(1)
    table.setExpanded(null)
  }, [table])
  const { view, setBasis, setWithFree } = useProfitabilityView(resetPosition)

  const refresh = useRefresh()
  // Прогон могли запустить в другой вкладке или вовсе не вы — кнопка обязана
  // это показывать, иначе четверо коллег нажмут её впустую.
  const sync = useSyncStatus()

  const query = useProfitability(
    {
      ...table.applied,
      page: table.page,
      ordering: table.ordering,
      pageSize: table.pageSize,
    },
    view
  )
  const data = query.data

  // Только идентификатор: снимок строки после «Обновить» показывал бы
  // старые числа рядом со свежим разбором.
  const [pickedId, setPickedId] = React.useState<number | null>(null)

  // Через `useMemo`, а не `?? []`: пустой литерал — новый объект на каждую
  // отрисовку, и масштаб полос пересчитывался бы бесконечно.
  const rows = React.useMemo(() => data?.results ?? [], [data])
  const picked = rows.find((row) => row.product_id === pickedId) ?? null
  const pageCount = data ? Math.max(1, Math.ceil(data.count / table.pageSize)) : 1
  const scale = React.useMemo(() => maxProfit(rows), [rows])

  return (
    <Page>
      <PageHeader
        title="Прибыльность"
        subtitle="На чём зарабатываем и на чём теряем"
        syncedAt={data?.synced_at ?? null}
        onRefresh={() => refresh.mutate()}
        refreshing={refresh.isPending || sync.running}
        refreshNote={refreshNote(refresh, sync.running, sync)}
        onExport={() => {
          window.location.assign(
            exportUrl({ ...table.applied, ordering: table.ordering }, view)
          )
        }}
      />

      <FiltersBar
        value={table.filters}
        onChange={table.changeFilters}
        onReset={table.resetFilters}
        searchPlaceholder={SEARCH_PLACEHOLDER}
        searchLabel={SEARCH_LABEL}
        extra={
          <ViewToggle view={view} onBasis={setBasis} onFree={setWithFree} />
        }
      />

      {data ? (
        <WarningStrip
          marketplaces={data.marketplaces}
          revenue={data.totals.revenue_kopecks}
        />
      ) : null}

      {/* Масштаб полос прибыли — наибольшая на показанной странице.
          Считается здесь: колонка о соседях по странице не знает. */}
      <ProfitScaleContext value={scale}>
        <DataTable
          columns={COLUMNS}
          rows={rows}
          rowKey={(row) => row.product_id}
          loading={query.isPending}
          // Приглушаются только устаревшие данные — те, что показаны, пока
          // едут новые после смены фильтра или базы.
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
              ? "Под эти фильтры товары не попали"
              : "За этот период ничего не продавали"
          }
          emptyHint={
            table.activeCount > 0
              ? "Попробуйте расширить период или изменить запрос."
              : "Прибыльность считает МойСклад. Данные появятся после первой синхронизации."
          }
          renderDetail={(row) => <RowDetail row={row} />}
          expandedKey={table.expanded}
          onToggle={(row) =>
            table.setExpanded((current) =>
              current === row.product_id ? null : row.product_id
            )
          }
          onOpen={(row) => setPickedId(row.product_id)}
          totals={data ? totalsFor(data.totals) : undefined}
          sort={table.sort}
          onSort={table.changeSort}
        />
      </ProfitScaleContext>

      {data && (rows.length > 0 || table.page > 1) ? (
        <TableFooter
          // Оба числа — про показанные строки: подвал описывает то, что
          // видно, а не всю выборку.
          summary={`${withPlural(data.count, "товар", "товара", "товаров")} · ${withPlural(Math.round(Number(data.totals.quantity)), "штука", "штуки", "штук")}`}
          page={table.page}
          pageCount={pageCount}
          pageSize={table.pageSize}
          onPage={table.setPage}
          onPageSize={table.setPageSize}
        />
      ) : null}

      {/* Пять блоков под таблицей и свёрнуты, как на соседних страницах.
          Порядок — от общего к частному: сколько заработали, где число
          нельзя читать буквально, чего стоят подарки, на какой линейке
          держится заработок, что осталось за пределами расчёта. */}
      {data ? (
        <>
          <Summary
            totals={data.totals}
            coverage={data.coverage}
            marketplaces={data.marketplaces}
          />
          <Marketplaces marketplaces={data.marketplaces} />
          <FreeAndLosses coverage={data.coverage} losses={data.losses} />
          <Families families={data.families} />
          <Coverage coverage={data.coverage} />
        </>
      ) : null}

      {/* Разбор — для узкого экрана и телефона. На широком он раскрывается
          прямо в строке. */}
      {screen !== "wide" ? (
        <DetailDrawer
          open={picked !== null}
          title={picked?.name ?? ""}
          subtitle={picked?.article}
          onClose={() => setPickedId(null)}
        >
          {picked ? <RowDetail row={picked} inDrawer /> : null}
        </DetailDrawer>
      ) : null}
    </Page>
  )
}
