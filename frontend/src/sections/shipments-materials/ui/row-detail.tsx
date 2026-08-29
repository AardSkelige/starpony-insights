import {
  useMaterialDetail,
  type ShipmentMaterialRow,
} from "@/sections/shipments-materials/api"
import { CoverageSection } from "@/sections/shipments-materials/ui/coverage-section"
import {
  BreakdownSection,
  PriceSection,
  TotalsSection,
} from "@/sections/shipments-materials/ui/detail-sections"
import {
  DistributionSection,
  RatesSection,
} from "@/sections/shipments-materials/ui/rates-section"
import type { TableSelection } from "@/shared/api/table-query"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { FailedPanel } from "@/shared/components/detail/failed-panel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs"
import { withPlural } from "@/shared/lib/plural"

type Props = {
  row: ShipmentMaterialRow
  query: TableSelection
  /** В выдвижной панели строка закрыта затемнением — её числа надо повторить. */
  repeatRowNumbers?: boolean
  /**
   * Разделы за переключателем, а не подряд.
   *
   * На телефоне запас, цена, норма и распределение подряд — это долгая
   * прокрутка внутри панели, которая сама уже перекрывает список. Вкладки
   * укладывают их в один экран. На широком месте хватает, и прятать
   * за нажатие то, что видно целиком, значит добавить работу на ровном месте.
   */
  tabbed?: boolean
}

/**
 * Разбор материала: хватит ли, почём, сколько на изделие, где сидит.
 *
 * **Порядок задан тем, как часто спрашивают.** Первым — запас: единственное
 * число, требующее действия сегодня. Прежде первым шёл разбор по техкартам,
 * и замер показал, что объяснять там почти нечего: у 100 материалов из 161
 * расход равен проданному один к одному, а несколько путей — у одного.
 *
 * **Разбор по техкартам не удалён — он ушёл вниз и свернулся.** Это
 * единственное место, где видно, что отдушка приходит в шампунь двумя путями
 * и 1,02 г на изделие не описка. Свёрнутым он и стоит ровно столько,
 * сколько стоит: нужен одному материалу из ста шестидесяти одного.
 */
export function RowDetail({
  row,
  query,
  repeatRowNumbers = false,
  tabbed = false,
}: Props) {
  const detail = useMaterialDetail(row.material_id, query)

  const breakdown = detail.data ? (
    <CollapsibleNote
      title="Разбор по техкартам"
      headline={breakdownNote(detail.data)}
    >
      <BreakdownSection detail={detail} row={row} bare />
    </CollapsibleNote>
  ) : null

  if (tabbed) {
    return (
      <Tabs defaultValue="stock" className="gap-3">
        <TabsList className="w-full">
          {/* Запас первой вкладкой: он — причина открыть панель. */}
          <TabsTrigger value="stock">Запас</TabsTrigger>
          <TabsTrigger value="price">Цена</TabsTrigger>
          <TabsTrigger value="where">Где сидит</TabsTrigger>
        </TabsList>

        <TabsContent value="stock" className="flex flex-col gap-5">
          {repeatRowNumbers ? <TotalsSection row={row} /> : null}
          <CoverageSection detail={detail} row={row} bare />
        </TabsContent>

        <TabsContent value="price">
          <PriceSection detail={detail} row={row} bare />
        </TabsContent>

        <TabsContent value="where" className="flex flex-col gap-5">
          <RatesSection detail={detail} row={row} bare />
          <DistributionSection detail={detail} row={row} />
          {breakdown}
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
    <div className="flex flex-col gap-4 p-4">
      <div className="grid gap-x-8 gap-y-5 lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-5">
          {repeatRowNumbers ? <TotalsSection row={row} /> : null}
          <CoverageSection detail={detail} row={row} />
          <PriceSection detail={detail} row={row} />
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          <RatesSection detail={detail} row={row} />
          <DistributionSection detail={detail} row={row} />
        </div>
      </div>

      {breakdown}
    </div>
  )
}

/**
 * Заголовок свёрнутого разбора несёт главное и в закрытом виде.
 *
 * «59 изделий · у 3 материал приходит несколькими путями» — по этой строке
 * видно, стоит ли раскрывать. Блок, который закрытым говорит только
 * «Подробности», никто не откроет.
 *
 * Оба числа приходят с сервера и описывают **все** источники. Считать
 * многопутёвые по показанным двадцати нельзя: у воды их пятьдесят девять,
 * и заголовок утверждал бы «в каждое одним путём», хотя многопутёвое
 * изделие могло стоять двадцать первым — блок обещал бы, что раскрывать
 * нечего, ровно там, где ради этого он и существует.
 */
function breakdownNote(data: {
  sources_count: number
  multi_path_count: number
}): string {
  return [
    withPlural(data.sources_count, "изделие", "изделия", "изделий"),
    data.multi_path_count > 0
      ? `у ${data.multi_path_count} материал приходит несколькими путями`
      : "в каждое материал приходит одним путём",
  ].join(" · ")
}
