import {
  useMaterialDetail,
  type ShipmentMaterialRow,
  type ShipmentMaterialsQuery,
} from "@/sections/shipments-materials/api"
import {
  BreakdownSection,
  PriceSection,
  StockSection,
  TotalsSection,
} from "@/sections/shipments-materials/ui/detail-sections"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs"

type Props = {
  row: ShipmentMaterialRow
  query: Omit<ShipmentMaterialsQuery, "page">
  /** В выдвижной панели строка закрыта затемнением — её числа надо повторить. */
  repeatRowNumbers?: boolean
  /**
   * Разделы за переключателем, а не подряд.
   *
   * На телефоне разбор, цена и остаток подряд — это долгая прокрутка внутри
   * панели, которая сама уже перекрывает список. Вкладки укладывают их
   * в один экран. На широком месте хватает, и прятать за нажатие то,
   * что видно целиком, значит добавить работу на ровном месте.
   */
  tabbed?: boolean
}

export function RowDetail({
  row,
  query,
  repeatRowNumbers = false,
  tabbed = false,
}: Props) {
  const detail = useMaterialDetail(row.material_id, query)

  if (tabbed) {
    return (
      <Tabs defaultValue="breakdown" className="gap-3">
        <TabsList className="w-full">
          {/* Разбор первой вкладкой: он — причина открыть панель. */}
          <TabsTrigger value="breakdown">Разбор</TabsTrigger>
          <TabsTrigger value="price">Цена</TabsTrigger>
          <TabsTrigger value="stock">Остаток</TabsTrigger>
        </TabsList>

        <TabsContent value="breakdown" className="flex flex-col gap-5">
          {repeatRowNumbers ? <TotalsSection row={row} /> : null}
          <BreakdownSection detail={detail} row={row} bare />
        </TabsContent>

        <TabsContent value="price">
          <PriceSection detail={detail} row={row} bare />
        </TabsContent>

        <TabsContent value="stock">
          <StockSection detail={detail} uom={row.uom} bare />
        </TabsContent>
      </Tabs>
    )
  }

  return (
    <div className="grid gap-x-8 gap-y-5 p-4 lg:grid-cols-2">
      {/* Разбор слева и первым: у воды он длинный, и правая колонка
          с ценой не должна ждать, пока он кончится. */}
      <BreakdownSection detail={detail} row={row} />
      <div className="flex flex-col gap-5">
        {repeatRowNumbers ? <TotalsSection row={row} /> : null}
        <PriceSection detail={detail} row={row} />
        <StockSection detail={detail} uom={row.uom} />
      </div>
    </div>
  )
}
