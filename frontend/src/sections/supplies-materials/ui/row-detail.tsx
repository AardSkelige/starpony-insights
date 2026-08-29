import {
  useSupplyMaterialDetail,
  type SupplyMaterialRow,
} from "@/sections/supplies-materials/api"
import {
  PriceSection,
  TotalsSection,
} from "@/sections/supplies-materials/ui/detail-sections"
import { PurchasesSection } from "@/sections/supplies-materials/ui/purchase-list"
import { SuppliersSection } from "@/sections/supplies-materials/ui/supplier-list"
import type { TableSelection } from "@/shared/api/table-query"
import { FailedPanel } from "@/shared/components/detail/failed-panel"
import { StockSection } from "@/shared/components/detail/stock"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs"

// Остаток известен не по всем материалам. За вкладкой пустота читается
// как поломка, поэтому отсутствие остатка говорится словами.
const NO_STOCK = "Остатка по этому материалу в отчёте МойСклада нет."

type Props = {
  row: SupplyMaterialRow
  query: TableSelection
  /** В выдвижной панели строка закрыта затемнением — её числа надо повторить. */
  repeatRowNumbers?: boolean
  /**
   * Разделы за переключателем, а не подряд.
   *
   * На телефоне цена, шесть закупок и поставщики подряд — это долгая
   * прокрутка внутри панели, которая сама уже перекрывает список. Вкладки
   * укладывают их в один экран. На широком месте хватает, и прятать
   * за нажатие то, что видно целиком, значит добавить работу на ровном месте.
   */
  tabbed?: boolean
}

export function RowDetail({
  row,
  query,
  repeatRowNumbers = false,
  tabbed = false,
}: Props) {
  const detail = useSupplyMaterialDetail(row.material_id, query)

  if (tabbed) {
    return (
      <Tabs defaultValue="price" className="gap-3">
        <TabsList className="w-full">
          {/* Цена первой вкладкой: она — причина открыть панель. */}
          <TabsTrigger value="price">Цена</TabsTrigger>
          <TabsTrigger value="purchases">Закупки</TabsTrigger>
          <TabsTrigger value="suppliers">Поставщики</TabsTrigger>
        </TabsList>

        <TabsContent value="price" className="flex flex-col gap-5">
          {repeatRowNumbers ? <TotalsSection row={row} /> : null}
          <PriceSection detail={detail} row={row} bare />
          <StockSection detail={detail} uom={row.uom} emptyNote={NO_STOCK} />
        </TabsContent>

        <TabsContent value="purchases">
          <PurchasesSection detail={detail} row={row} bare />
        </TabsContent>

        <TabsContent value="suppliers">
          <SuppliersSection detail={detail} row={row} bare />
        </TabsContent>
      </Tabs>
    )
  }

  // На широком экране блоки лежат рядом, и сообщение об ошибке нужно одно:
  // четыре одинаковых «Не удалось» с четырьмя кнопками повторяют один запрос.
  if (detail.isError) {
    return <FailedPanel onRetry={() => detail.refetch()} />
  }

  return (
    <div className="grid gap-x-8 gap-y-5 p-4 lg:grid-cols-2">
      {/* Слева цена и график — то, ради чего строку раскрывают. */}
      <div className="flex min-w-0 flex-col gap-5">
        {repeatRowNumbers ? <TotalsSection row={row} /> : null}
        <PriceSection detail={detail} row={row} />
        <PurchasesSection detail={detail} row={row} />
      </div>
      <div className="flex min-w-0 flex-col gap-5">
        <SuppliersSection detail={detail} row={row} />
        <StockSection detail={detail} uom={row.uom} />
      </div>
    </div>
  )
}
