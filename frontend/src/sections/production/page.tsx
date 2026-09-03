import * as React from "react"

import { useBatch, useProducts } from "@/sections/production/api"
import { useBatchParams } from "@/sections/production/use-batch"
import { useColumnHeight } from "@/sections/production/use-column-height"
import { Answer } from "@/sections/production/ui/answer"
import { Horizon } from "@/sections/production/ui/horizon"
import { NeedsList, NeedsListHeader } from "@/sections/production/ui/needs-list"
import { Problems } from "@/sections/production/ui/problems"
import { runningOut } from "@/sections/production/running-out"
import {
  ProductList,
  ProductListHeader,
} from "@/sections/production/ui/product-list"
import { refreshNote, useRefresh, useSyncStatus } from "@/shared/api/sync"
import { FiltersBar } from "@/shared/components/filters/bar"
import { Page } from "@/shared/components/page"
import { PageHeader } from "@/shared/components/page-header"
import { WarningStrip } from "@/shared/components/warning-strip"
import { Button } from "@/shared/ui/button"
import { withPlural } from "@/shared/lib/plural"

const SEARCH_PLACEHOLDER = "Название или артикул"
const SEARCH_LABEL = "Поиск по товарам"

/**
 * «Расчёт производства»: что варить и что для этого закупить.
 *
 * **Одна цепочка, а не два таба.** Вопросы «что производить» и «что закупить»
 * идут друг за другом, а не рядом: сырьё нужно под ту партию, которую решили
 * выпустить. Разрежь их вкладками — и человеку придётся переносить числа
 * через границу руками.
 *
 * Отсюда две колонки: слева выбор, справа последствия. Прибавил десять
 * флаконов — тут же увидел, что докупать. Правая колонка не опустошается
 * на время запроса (`keepPreviousData`): связь между причиной и следствием
 * иначе пришлось бы держать в голове.
 *
 * **На узком экране колонки складываются в одну**, и порядок меняется:
 * ответ уезжает наверх. На широком он справа и виден рядом со списком,
 * на телефоне — под шапкой, потому что прокручивать до него значит потерять
 * то самое «тут же».
 *
 * **Разбиения на страницы нет.** Партию нельзя собирать, если половина
 * товаров на второй странице; товаров с артикулом 57, материалов под партию
 * до сотни — множество закрытое и обозримое.
 */
export function ProductionPage() {
  const params = useBatchParams()
  // Высота колонок меряется, а не подбирается числом: они начинаются
  // под шапкой и фильтрами, а те меняются от переноса и от полосы
  // предупреждения.
  const { gridRef, maxHeight } = useColumnHeight()

  const refresh = useRefresh()
  // Прогон могли запустить в другой вкладке или вовсе не вы — кнопка обязана
  // это показывать, иначе четверо коллег нажмут её впустую.
  const sync = useSyncStatus()

  const products = useProducts({
    dateFrom: params.applied.dateFrom,
    dateTo: params.applied.dateTo,
    search: params.applied.search,
    horizon: params.horizon,
  })
  const rows = React.useMemo(() => products.data?.rows ?? [], [products.data])
  // Партия уходит как есть: голый артикул означает «посчитай сам», и считает
  // это сервер. Разрешай мы количества здесь — по списку, суженному
  // поиском, — партия молча теряла бы всё, чего в найденном не оказалось.
  const batch = useBatch(params.picked, {
    dateFrom: params.applied.dateFrom,
    dateTo: params.applied.dateTo,
    search: "",
    horizon: params.horizon,
  })

  const needs = React.useMemo(() => batch.data?.materials ?? [], [batch.data])
  // Свои у каждой колонки: свернуть спокойные товары и свернуть материалы,
  // которых хватает, — разные решения, и раскрывать их вместе незачем.
  const [showAllProducts, setShowAllProducts] = React.useState(false)
  const [showAllNeeds, setShowAllNeeds] = React.useState(false)

  const summary = batch.data?.summary
  const attention =
    (summary?.below_min_now_count ?? 0) + (summary?.below_min_after_count ?? 0)

  return (
    <Page>
      <PageHeader
        title="Расчёт производства"
        subtitle="Что варить и что для этого закупить"
        syncedAt={products.data?.synced_at ?? null}
        onRefresh={() => refresh.mutate()}
        refreshing={refresh.isPending || sync.running}
        refreshNote={refreshNote(refresh, sync.running)}
      />

      {/* «Период» здесь подписан иначе: он не сужает выборку, а задаёт окно,
          из которого берётся темп продаж. Безымянным он не объяснял ничего. */}
      <FiltersBar
        value={{
          dateFrom: params.raw.dateFrom,
          dateTo: params.raw.dateTo,
          pickId: null,
          search: params.raw.search,
        }}
        onChange={(patch) =>
          params.setFilters({
            dateFrom: patch.dateFrom,
            dateTo: patch.dateTo,
            search: patch.search,
          })
        }
        onReset={params.reset}
        periodLabel="Спрос за период"
        searchPlaceholder={SEARCH_PLACEHOLDER}
        searchLabel={SEARCH_LABEL}
        extra={<Horizon value={params.horizon} onChange={params.setHorizon} />}
      />

      {batch.data ? <Problems lines={batch.data.lines} /> : null}

      {/* Обе колонки — со своей прокруткой и высотой в экран. Без этого
          страница росла на три экрана: пятьдесят семь товаров слева и сотня
          материалов справа, а шапка с фильтрами и «Обновить» уезжала вверх.
          На узком экране прокрутки нет — там колонки сложены в одну,
          и вложенная воевала бы с прокруткой страницы. */}
      <div
        ref={gridRef}
        className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:items-start"
      >
        <section
          style={{ maxHeight }}
          className="flex min-w-0 flex-col rounded-lg border bg-card lg:sticky lg:top-4"
        >
          <header className="min-w-0 shrink-0 border-b px-3 py-2.5">
            {products.data ? (
              <ProductListHeader
                summary={products.data.summary}
                horizon={params.horizon}
              />
            ) : null}
          </header>

          <div className="min-w-0 flex-1 lg:overflow-y-auto">
            <ProductList
              rows={rows}
              picked={params.picked}
              loading={products.isPending}
              showAll={showAllProducts}
              onToggleAll={() => setShowAllProducts((shown) => !shown)}
              onToggle={params.toggle}
              onQuantity={params.setQuantity}
            />
          </div>

          <footer className="flex shrink-0 flex-wrap items-center gap-2 border-t px-3 py-2">
            <Button
              variant="outline"
              size="sm"
              // Ровно то, что кончается, — как обещает подпись.
              // До этого кнопка брала все пятьдесят семь, включая
              // спрятанные за «их пока хватает».
              onClick={() => params.takeAll(runningOut(rows, params.picked))}
              disabled={!rows.length}
            >
              Взять всё, что кончается
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={params.clear}
              disabled={!Object.keys(params.picked).length}
            >
              Очистить партию
            </Button>
          </footer>
        </section>

        {/* Ответ и предупреждение остаются на месте, прокручивается только
            список закупки: они и есть то, ради чего выбрана двухколоночная
            раскладка. */}
        <div
          style={{ maxHeight }}
          className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-4"
        >
          {summary ? <Answer summary={summary} /> : null}

          {attention > 0 ? (
            <WarningStrip>
              <span className="font-medium">
                Неснижаемый остаток задет у{" "}
                {withPlural(attention, "позиции", "позиций", "позиций")}.
              </span>{" "}
              <span className="text-muted-foreground">
                Это отдельный сигнал, а не нехватка: партия пройдёт, но
                закупаться придётся сразу. Подробности — в строках ниже.
              </span>
            </WarningStrip>
          ) : null}

          <section className="flex min-w-0 flex-col overflow-hidden rounded-lg border bg-card lg:min-h-0">
            <header className="flex shrink-0 items-baseline justify-between gap-3 border-b px-3 py-2.5">
              <NeedsListHeader
                materials={summary?.materials_count ?? 0}
                shortages={summary?.shortages_count ?? 0}
                unknown={summary?.unknown_stock_count ?? 0}
              />
            </header>
            <div className="min-w-0 flex-1 lg:overflow-y-auto">
              <NeedsList
                needs={needs}
                showAll={showAllNeeds}
                onToggleAll={() => setShowAllNeeds((shown) => !shown)}
              />
            </div>
          </section>
        </div>
      </div>
    </Page>
  )
}
