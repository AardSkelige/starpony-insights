import * as React from "react"

import { exportUrl, useChannels } from "@/sections/channels/api"
import { COLUMNS, SORT_KEYS, totalsFor } from "@/sections/channels/columns"
import { Coverage } from "@/sections/channels/ui/coverage"
import { Picture } from "@/sections/channels/ui/picture"
import { RowDetail } from "@/sections/channels/ui/row-detail"
import { refreshNote, useRefresh, useSyncStatus } from "@/shared/api/sync"
import { DataTable } from "@/shared/components/data-table"
import { DetailDrawer } from "@/shared/components/detail-drawer"
import { FiltersBar } from "@/shared/components/filters/bar"
import { ConsignmentNote } from "@/shared/components/consignment"
import { Page } from "@/shared/components/page"
import { PageHeader } from "@/shared/components/page-header"
import { TableFooter } from "@/shared/components/table-footer"
import { useScreen } from "@/shared/hooks/use-screen"
import { useTableParams } from "@/shared/hooks/use-table-params"
import { withPlural } from "@/shared/lib/plural"

const SEARCH_PLACEHOLDER = "Канал или покупатель"
const SEARCH_LABEL = "Поиск по каналам и покупателям"

/**
 * «Каналы продаж»: где продаём и сколько это приносит.
 *
 * **Открывается как все остальные:** шапка, фильтры, таблица. Графики —
 * свёрнутым блоком под ней (`ui/picture.tsx`), вместе со сводкой. Сначала
 * они стояли сверху, потому что отвечают быстрее строк; владелец поправил
 * 30.08, и довод сильнее: привычка, наработанная на четырёх страницах,
 * дороже выигранной секунды на пятой.
 *
 * **Графики описывают выборку, а не страницу таблицы.** Поиск сужает
 * список строк — он про «что показано»; период меняет то, что посчитано.
 * Оставь мы в полосах найденное, единственная строка заняла бы всю ширину
 * со стопроцентной долей.
 */
export function ChannelsPage() {
  const screen = useScreen()
  // Минус обязателен: «revenue» значит «по возрастанию», и страница
  // открывалась бы с канала, принёсшего 19 540 ₽, вместо того, на который
  // приходится треть выручки.
  const table = useTableParams({
    defaultSort: "-revenue",
    sortKeys: SORT_KEYS,
    // Справочника у этой страницы нет: канал и есть строка таблицы.
    // Выбери его фильтром — в таблице останется одна строка, а сравнивать
    // станет не с чем.
  })

  const refresh = useRefresh()
  // Прогон могли запустить в другой вкладке или вовсе не вы — кнопка обязана
  // это показывать, иначе четверо коллег нажмут её впустую.
  const sync = useSyncStatus()

  const query = useChannels({
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
  const picked = rows.find((row) => row.channel_id === pickedId) ?? null
  const pageCount = data ? Math.max(1, Math.ceil(data.count / table.pageSize)) : 1

  return (
    <Page>
      <PageHeader
        title="Каналы продаж"
        subtitle="Где продаём и сколько это приносит"
        syncedAt={data?.synced_at ?? null}
        onRefresh={() => refresh.mutate()}
        refreshing={refresh.isPending || sync.running}
        refreshNote={refreshNote(refresh, sync.running, sync)}
        onExport={() => {
          window.location.assign(
            exportUrl({ ...table.applied, ordering: table.ordering })
          )
        }}
      />

      <FiltersBar
        value={table.filters}
        onChange={table.changeFilters}
        onReset={table.resetFilters}
        searchPlaceholder={SEARCH_PLACEHOLDER}
        searchLabel={SEARCH_LABEL}
      />

      {/* Единственное предупреждение страницы, которое не свёрнуто: без него
          выручка читается как заработанная, а треть её — товар, отгруженный
          на реализацию. Считается по показанному и сужается фильтрами
          вместе со строками. */}
      {data ? <ConsignmentNote share={data.totals.consignment} /> : null}

      <DataTable
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.channel_id}
        loading={query.isPending}
        // Приглушаются только устаревшие данные — те, что показаны, пока
        // едут новые после смены фильтра или страницы.
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
            ? "Под эти фильтры каналы не попали"
            : "За этот период ничего не продавали"
        }
        emptyHint={
          table.activeCount > 0
            ? "Попробуйте расширить период или изменить запрос."
            : "Каналы берутся из отгрузок МойСклада. Данные появятся после первой синхронизации."
        }
        renderDetail={(row) =>
          data ? <RowDetail row={row} dynamics={data.dynamics} /> : null
        }
        expandedKey={table.expanded}
        onToggle={(row) =>
          table.setExpanded((current) =>
            current === row.channel_id ? null : row.channel_id
          )
        }
        onOpen={(row) => setPickedId(row.channel_id)}
        totals={data ? totalsFor(data.totals) : undefined}
        sort={table.sort}
        onSort={table.changeSort}
      />

      {data && (rows.length > 0 || table.page > 1) ? (
        <TableFooter
          // Оба числа — про показанные строки. Отгрузки из `coverage`
          // описывают выборку целиком, и при поиске подвал читался бы как
          // «1 канал · 306 отгрузок», где 306 относятся ко всем девяти.
          summary={`${withPlural(data.count, "канал", "канала", "каналов")} · ${withPlural(data.totals.shipments_count, "отгрузка", "отгрузки", "отгрузок")}`}
          page={table.page}
          pageCount={pageCount}
          pageSize={table.pageSize}
          onPage={table.setPage}
          onPageSize={table.setPageSize}
        />
      ) : null}

      {/* Оба блока под таблицей и свёрнуты, как на соседних страницах:
          главное здесь строки. Графики отвечают на «как устроены продажи»,
          сводка — на «полное ли то, что показано»; вопросы разные,
          поэтому блока два, а не один. */}
      {data ? <Picture data={data} /> : null}
      {data ? <Coverage coverage={data.coverage} /> : null}

      {/* Разбор — для узкого экрана и телефона. На широком он раскрывается
          прямо в строке. */}
      {screen !== "wide" ? (
        <DetailDrawer
          open={picked !== null}
          title={picked?.name ?? ""}
          subtitle={
            picked
              ? `${withPlural(picked.shipments_count, "отгрузка", "отгрузки", "отгрузок")} · ${withPlural(picked.buyers_count, "покупатель", "покупателя", "покупателей")}`
              : undefined
          }
          onClose={() => setPickedId(null)}
        >
          {picked && data ? (
            <RowDetail row={picked} dynamics={data.dynamics} inDrawer />
          ) : null}
        </DetailDrawer>
      ) : null}
    </Page>
  )
}
