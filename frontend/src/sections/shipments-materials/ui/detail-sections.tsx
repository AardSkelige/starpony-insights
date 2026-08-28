import type {
  ShipmentMaterialRow,
  useMaterialDetail,
} from "@/sections/shipments-materials/api"
import { ExplainTree } from "@/sections/shipments-materials/ui/explain-tree"
import { Fact, Facts, Failed, Loading, Section } from "@/shared/components/detail"
import {
  formatDate,
  formatMoney,
  formatQuantity,
  formatUnitPrice,
} from "@/shared/lib/format"

/**
 * Блоки разбора материала.
 *
 * Отдельно от сборки: та решает только, показать их подряд или за
 * переключателем, а что внутри каждого — вопрос сам по себе.
 */
type Detail = ReturnType<typeof useMaterialDetail>

/** Числа самой строки — нужны там, где строка закрыта панелью. */
export function TotalsSection({ row }: { row: ShipmentMaterialRow }) {
  return (
    <Section title="За период" bare>
      <Facts>
        <Fact label="Израсходовано" value={formatQuantity(row.quantity, row.uom)} />
        <Fact
          label="Стоимость"
          value={row.cost_kopecks === null ? "—" : formatMoney(row.cost_kopecks)}
        />
        <Fact label="Изделий-источников" value={String(row.products_count)} />
      </Facts>
    </Section>
  )
}

/**
 * Откуда взялось число: изделия и пути по техкартам.
 *
 * Это причина, по которой панель открывают, — поэтому она идёт первой
 * и не прячется ни за какой второй уровень.
 */
export function BreakdownSection({
  detail,
  row,
  bare = false,
}: {
  detail: Detail
  row: ShipmentMaterialRow
  bare?: boolean
}) {
  const title = `Откуда взялись ${formatQuantity(row.quantity, row.uom)}`

  if (detail.isError) {
    return (
      <Section title={title} bare={bare}>
        <Failed onRetry={() => detail.refetch()} />
      </Section>
    )
  }

  if (detail.isPending) {
    return (
      <Section title={title} bare={bare}>
        <Loading count={4} />
      </Section>
    )
  }

  const data = detail.data
  if (!data) return null

  return (
    <Section
      title={title}
      note={
        data.sources_count > data.sources.length
          ? `показаны ${data.sources.length} из ${data.sources_count}`
          : undefined
      }
      bare={bare}
    >
      <ExplainTree sources={data.sources} rest={data.rest} uom={row.uom} />
    </Section>
  )
}

/**
 * Откуда взялась цена: документ, дата, поставщик.
 *
 * Число, посчитанное по цене, обязано назвать её источник — иначе колонка
 * «Стоимость» остаётся суммой, за которую никто не отвечает.
 */
export function PriceSection({
  detail,
  row,
  bare = false,
}: {
  detail: Detail
  row: ShipmentMaterialRow
  bare?: boolean
}) {
  // Сбой нельзя показывать как факт учёта. Без этой ветки не доехавший
  // ответ рисовал «ни разу не закупался» — утверждение о данных, которых
  // мы не видели. На телефоне цена лежит за своей вкладкой, и сообщение
  // об ошибке из соседнего блока человеку даже не видно.
  if (detail.isError) {
    return (
      <Section title="Цена закупки" bare={bare}>
        <Failed onRetry={() => detail.refetch()} />
      </Section>
    )
  }

  if (detail.isPending) {
    return (
      <Section title="Цена закупки" bare={bare}>
        <Loading count={3} />
      </Section>
    )
  }

  const price = detail.data?.price

  // Цены нет вовсе — это факт учёта, и он говорится словами, а не пустотой.
  if (!price) {
    return (
      <Section title="Цена закупки" bare={bare}>
        <p className="py-1.5 text-sm text-muted-foreground">
          Этот материал ни разу не закупался по ненулевой цене, поэтому
          стоимость израсходованного не посчитана. В сумму по странице
          он не входит.
        </p>
      </Section>
    )
  }

  const cost = detail.data?.cost_kopecks

  return (
    <Section title="Цена закупки" bare={bare}>
      <Facts>
        <Fact
          label="Цена за единицу"
          value={`${formatUnitPrice(price.price_kopecks)}${row.uom ? ` / ${row.uom}` : ""}`}
        />
        <Fact label="Документ" value={`Приёмка №${price.document_number}`} />
        <Fact label="Дата" value={formatDate(price.moment)} />
        <Fact label="Поставщик" value={price.supplier} />
        {cost !== null && cost !== undefined ? (
          <Fact label="Стоимость израсходованного" value={formatMoney(cost)} />
        ) : null}
      </Facts>
    </Section>
  )
}