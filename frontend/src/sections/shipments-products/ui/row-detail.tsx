import {
  useProductDetail,
  type ShipmentProductRow,
} from "@/sections/shipments-products/api"
import {
  ChannelsSection,
  DocumentsSection,
  PeriodSection,
  PriceSection,
} from "@/sections/shipments-products/ui/detail-sections"
import type { TableSelection } from "@/shared/api/table-query"
import { FailedPanel } from "@/shared/components/detail/failed-panel"
import { StockSection } from "@/shared/components/detail/stock"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs"

type Props = {
  row: ShipmentProductRow
  query: TableSelection
  /** В выдвижной панели строка закрыта затемнением — её числа надо повторить. */
  repeatRowNumbers?: boolean
  /**
   * Разделы за переключателем, а не подряд.
   *
   * На телефоне три блока подряд — это долгая прокрутка внутри панели, которая
   * сама уже перекрывает список. Вкладки укладывают их в один экран.
   * На широком экране переключатель не нужен: место есть, и прятать
   * за нажатие то, что видно целиком, значит добавить работу на ровном месте.
   */
  tabbed?: boolean
}

export function RowDetail({ row, query, repeatRowNumbers = false, tabbed = false }: Props) {
  const detail = useProductDetail(row.product_id, query)

  if (tabbed) {
    return (
      <Tabs defaultValue="totals" className="gap-3">
        <TabsList className="w-full">
          <TabsTrigger value="totals">Итоги</TabsTrigger>
          <TabsTrigger value="channels">Каналы</TabsTrigger>
          <TabsTrigger value="documents">Отгрузки</TabsTrigger>
        </TabsList>

        <TabsContent value="totals" className="flex flex-col gap-5">
          <PeriodSection row={row} always />
          <StockSection detail={detail} uom={row.uom} />
        </TabsContent>

        <TabsContent value="channels">
          <ChannelsSection detail={detail} uom={row.uom} bare />
        </TabsContent>

        <TabsContent value="documents">
          <DocumentsSection detail={detail} count={row.documents_count} bare />
        </TabsContent>
      </Tabs>
    )
  }

  // На широком экране блоки лежат рядом, и сообщение об ошибке нужно одно:
  // несколько одинаковых «Не удалось» с несколькими кнопками повторяют
  // один и тот же запрос.
  if (detail.isError) {
    return <FailedPanel onRetry={() => detail.refetch()} />
  }

  return (
    <div className="grid gap-x-8 gap-y-5 p-4 lg:grid-cols-2">
      <div className="flex flex-col gap-5">
        {repeatRowNumbers ? <PeriodSection row={row} always /> : <PriceSection row={row} />}
        <StockSection detail={detail} uom={row.uom} />
      </div>
      <div className="flex flex-col gap-5">
        <ChannelsSection detail={detail} uom={row.uom} />
        <DocumentsSection detail={detail} count={row.documents_count} />
      </div>
    </div>
  )
}
