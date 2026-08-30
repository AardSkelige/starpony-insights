import {
  useProductDetail,
  type ShipmentProductRow,
} from "@/sections/shipments-products/api"
import {
  ChannelsSection,
  PeriodSection,
  PriceSection,
  RecipientsSection,
} from "@/sections/shipments-products/ui/detail-sections"
import { TimelineSection } from "@/sections/shipments-products/ui/timeline"
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
          <TabsTrigger value="when">Когда</TabsTrigger>
          <TabsTrigger value="who">Кому</TabsTrigger>
        </TabsList>

        <TabsContent value="totals" className="flex flex-col gap-5">
          <PeriodSection row={row} always />
          <ChannelsSection detail={detail} uom={row.uom} />
          <StockSection detail={detail} uom={row.uom} />
        </TabsContent>

        <TabsContent value="when">
          <TimelineSection detail={detail} uom={row.uom} bare />
        </TabsContent>

        <TabsContent value="who" className="flex flex-col gap-5">
          <RecipientsSection detail={detail} uom={row.uom} />
          <RecipientsSection detail={detail} uom={row.uom} free />
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

  // Колонки делятся по смыслу и сходятся по высоте. Слева — **почём, когда
  // и через что**: цена, динамика, каналы. Справа — **кому**: покупатели,
  // получатели бесплатного и склад.
  //
  // Склад справа не по смыслу, а по высоте: слева девять полос каналов
  // и график, и без переноса правая колонка обрывалась на полпути.
  return (
    <div className="grid gap-x-6 gap-y-4 p-4 lg:grid-cols-2">
      <div className="flex flex-col gap-4">
        {repeatRowNumbers ? <PeriodSection row={row} always /> : <PriceSection row={row} />}
        <TimelineSection detail={detail} uom={row.uom} />
        <ChannelsSection detail={detail} uom={row.uom} />
      </div>
      <div className="flex flex-col gap-4">
        <RecipientsSection detail={detail} uom={row.uom} />
        <RecipientsSection detail={detail} uom={row.uom} free />
        <StockSection detail={detail} uom={row.uom} />
      </div>
    </div>
  )
}
