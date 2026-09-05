import * as React from "react"

import { exportUrl, useInventory } from "@/sections/inventory/api"
import { COLUMNS, SORT_KEYS, totalsFor } from "@/sections/inventory/columns"
import { useInventoryCuts } from "@/sections/inventory/use-cuts"
import { Coverage } from "@/sections/inventory/ui/coverage"
import { Cuts } from "@/sections/inventory/ui/cuts"
import { Documents } from "@/sections/inventory/ui/documents"
import { Repeats } from "@/sections/inventory/ui/repeats"
import { RowDetail } from "@/sections/inventory/ui/row-detail"
import { Worst } from "@/sections/inventory/ui/worst"
import { refreshNote, useRefresh, useSyncStatus } from "@/shared/api/sync"
import { DataTable } from "@/shared/components/data-table"
import { DetailDrawer } from "@/shared/components/detail-drawer"
import { FiltersBar } from "@/shared/components/filters/bar"
import { Page } from "@/shared/components/page"
import { PageHeader } from "@/shared/components/page-header"
import { TableFooter } from "@/shared/components/table-footer"
import { WarningStrip } from "@/shared/components/warning-strip"
import { useScreen } from "@/shared/hooks/use-screen"
import { useTableParams } from "@/shared/hooks/use-table-params"
import { formatDate } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

const SEARCH_PLACEHOLDER = "Название или артикул"
const SEARCH_LABEL = "Поиск по номенклатуре"

export function InventoryPage() {
  const screen = useScreen()
  // Минус обязателен: «money» значит «по возрастанию», и страница
  // открывалась бы с копеечных расхождений вместо тех, что дороже всего.
  const table = useTableParams({
    defaultSort: "-money",
    sortKeys: SORT_KEYS,
    // Периода нет: «что давно не считали» — состояние на сегодня, и период
    // не сузил бы выборку, а спрятал бы позиции, не попавшие ни в один
    // пересчёт, — то есть ровно те, ради которых страницу открывают.
    period: false,
  })
  const cuts = useInventoryCuts(() => table.setPage(1))

  const refresh = useRefresh()
  // Прогон могли запустить в другой вкладке или вовсе не вы — кнопка обязана
  // это показывать, иначе четверо коллег нажмут её впустую.
  const sync = useSyncStatus()

  const query = useInventory(
    {
      ...table.applied,
      page: table.page,
      ordering: table.ordering,
      pageSize: table.pageSize,
    },
    cuts.cuts
  )
  const data = query.data

  // Только идентификатор: снимок строки после «Обновить» показывал бы
  // старые числа рядом со свежим разбором.
  const [pickedId, setPickedId] = React.useState<number | null>(null)

  const rows = data?.results ?? []
  const picked = rows.find((row) => row.product_id === pickedId) ?? null
  const pageCount = data ? Math.max(1, Math.ceil(data.count / table.pageSize)) : 1

  return (
    <Page>
      <PageHeader
        title="Инвентаризация"
        subtitle="Когда пересчитывали каждую позицию и на сколько она не сошлась"
        syncedAt={data?.synced_at ?? null}
        onRefresh={() => refresh.mutate()}
        refreshing={refresh.isPending || sync.running}
        refreshNote={refreshNote(refresh, sync.running, sync)}
        onExport={() => {
          window.location.assign(
            exportUrl({ ...table.applied, ordering: table.ordering }, cuts.cuts)
          )
        }}
      />

      <FiltersBar
        value={table.filters}
        onChange={table.changeFilters}
        onReset={() => {
          table.resetFilters()
          cuts.reset()
        }}
        period={false}
        searchPlaceholder={SEARCH_PLACEHOLDER}
        searchLabel={SEARCH_LABEL}
        extra={
          <Cuts
            cuts={cuts.cuts}
            stores={data?.stores ?? []}
            folders={data?.folders ?? []}
            onChange={cuts.setCuts}
          />
        }
      />

      {/* Оговорка стоит выше чисел, которых касается: подсказку по наведению
          открывают, уже приняв решение по числу. Показывается только когда
          есть о чём предупредить — то есть когда деньги вообще посчитаны. */}
      {data && data.worst.diverged_count > 0 ? (
        <WarningStrip>
          {/* Коротко: на телефоне длинный текст занимал весь первый экран,
              и ни одной строки таблицы не оставалось. Про «не оценено»
              говорят итог таблицы и блок «Где не сходится» — повторять
              это здесь значит платить экраном за то, что уже сказано. */}
          <b>Деньги посчитаны нами, а не учётом.</b> В документах
          инвентаризации цена чаще всего не заполнена — МойСклад показывает
          по таким строкам 0 ₽ при живой недостаче. Здесь расхождение
          умножено на себестоимость <b>на сегодня</b>, поэтому с карточкой
          документа число не сойдётся.
        </WarningStrip>
      ) : null}

      <DataTable
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.product_id}
        loading={query.isPending}
        // Приглушаются только устаревшие данные — те, что показаны, пока
        // едут новые после смены разреза или страницы.
        refreshing={query.isPlaceholderData}
        // Тот же признак, что у кнопки и отметки свежести: чужой прогон
        // виден всем, и его результат подсвечивается так же, как свой.
        syncPending={refresh.isPending || sync.running}
        syncFailed={refresh.isError}
        dataVersion={query.dataUpdatedAt}
        error={query.isError}
        onRetry={() => query.refetch()}
        emptyTitle={
          table.activeCount > 0 || cuts.activeCount > 0
            ? "Под эти фильтры позиции не попали"
            : "Номенклатуры пока нет"
        }
        emptyHint={
          table.activeCount > 0 || cuts.activeCount > 0
            ? "Попробуйте выбрать другую папку или изменить запрос."
            : "Позиции берутся из номенклатуры МойСклада. Данные появятся после первой синхронизации."
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

      {data && (rows.length > 0 || table.page > 1) ? (
        <TableFooter
          // Оба числа — про показанные строки, с учётом поиска и разрезов.
          summary={`${withPlural(data.count, "позиция", "позиции", "позиций")} · не считали ${data.totals.never_counted_count}`}
          page={table.page}
          pageCount={pageCount}
          pageSize={table.pageSize}
          onPage={table.setPage}
          onPageSize={table.setPageSize}
        />
      ) : null}

      {/* Блоки — под таблицей и свёрнуты, как на восьми соседних страницах.
          Оба вопроса страницы видны их заголовками, не раскрывая ни одного. */}
      {data ? (
        <>
          <Coverage coverage={data.coverage} />
          <Worst worst={data.worst} />
          <Repeats repeats={data.repeats} />
          <Documents documents={data.documents} />
        </>
      ) : null}

      {/* Разбор — для узкого экрана и телефона. На широком он раскрывается
          прямо в строке. */}
      {screen !== "wide" ? (
        <DetailDrawer
          open={picked !== null}
          title={picked?.name ?? ""}
          subtitle={
            picked
              ? picked.last_moment
                ? `${formatDate(picked.last_moment)} · ${picked.last_store}`
                : "не пересчитывали ни разу"
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
