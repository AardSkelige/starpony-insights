import type { Channels } from "@/sections/channels/api"
import { Section } from "@/shared/components/detail"
import { Explain } from "@/shared/components/explain"
import { formatShare } from "@/shared/lib/format"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip"

type Standing = Channels["standings"][number]

/**
 * Деньги против отгрузок — две доли одного канала рядом.
 *
 * **Это главный вопрос страницы, и одним числом он не отвечается.** Озон даёт
 * 44 % отгрузок и 17 % выручки, «Точка продаж» — 11 % и 37 %. В таблице обе
 * величины стоят, но сравнивать их приходится глазами по двум колонкам через
 * всю ширину; здесь они лежат друг под другом, и расхождение видно как
 * разница длин, без чтения чисел вовсе.
 *
 * **Две полосы, а не одна с двумя цветами.** Это две доли одного и того же
 * множества, а не части целого: складывать их бессмысленно, и сложённая
 * полоса обещала бы сумму, которой нет.
 *
 * Верхняя — деньги, нижняя — отгрузки, порядок один во всех строках:
 * иначе пришлось бы сверяться с легендой на каждой.
 */
export function PaceCard({ standings }: { standings: Standing[] }) {
  // Обе полосы меряются одной линейкой — наибольшей долей на карточке.
  // Своя шкала у каждой строки сделала бы «берёт чеком» неотличимым
  // от «берёт числом»: обе полосы всегда упирались бы в край.
  const scale = Math.max(
    ...standings.flatMap((item) => [
      Number(item.revenue_share ?? 0),
      Number(item.shipments_share ?? 0),
    ]),
    0.0001
  )

  return (
    <Section
      title="Деньги против отгрузок"
      note="две доли одного канала"
      explain={
        <Explain>
          Сверху — какую часть <b>выручки</b> даёт канал, снизу — какую часть{" "}
          <b>отгрузок</b>. Обе от одной и той же выборки. Полосы разной длины
          значат, что канал берёт либо чеком, либо числом: у Озона 44 %
          отгрузок и 17 % денег, у «Точки продаж» наоборот.
        </Explain>
      }
    >
      {/* Легенда обязательна: серий две, и различаются они только цветом.
          Без неё верхняя полоса ничем не отличима от нижней, и «берёт чеком»
          читается наоборот. Порядок легенды тот же, что у полос в строке. */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 pb-2.5 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-1.5 w-4 rounded-full bg-primary" />
          доля в выручке
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-1.5 w-4 rounded-full bg-muted-foreground" />
          доля в отгрузках
        </span>
      </div>

      <div className="flex flex-col gap-2.5">
        {standings.map((item) => (
          <PaceRow key={item.channel_id} item={item} scale={scale} />
        ))}
      </div>
    </Section>
  )
}

function PaceRow({ item, scale }: { item: Standing; scale: number }) {
  const money = Number(item.revenue_share ?? 0)
  const count = Number(item.shipments_share ?? 0)

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <div className="flex min-w-0 items-center gap-3 text-sm">
            <span className="w-24 shrink-0 truncate text-xs text-muted-foreground">
              {item.name}
            </span>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <Lane share={money} scale={scale} tone="money" />
              <Lane share={count} scale={scale} tone="count" />
            </span>
            {/* Вывод словом, а не две доли цифрами: расхождение длин уже
                показано, и колонка процентов рядом только соревнуется с ним
                за внимание. Точные доли — в подсказке. */}
            <span className="w-24 shrink-0 text-right text-xs text-muted-foreground">
              {verdict(money, count)}
            </span>
          </div>
        }
      />
      <TooltipContent>
        {formatShare(item.revenue_share)} выручки при{" "}
        {formatShare(item.shipments_share)} отгрузок
      </TooltipContent>
    </Tooltip>
  )
}

/**
 * Дорожка во всю ширину, а не голая полоса: без неё доли не с чем сравнивать,
 * кроме друг друга, и «мало» перестаёт отличаться от «почти всё».
 */
function Lane({
  share,
  scale,
  tone,
}: {
  share: number
  scale: number
  tone: "money" | "count"
}) {
  return (
    <span className="h-1.5 w-full rounded-full bg-muted">
      <span
        className={
          tone === "money"
            ? "block h-full rounded-full bg-primary"
            : "block h-full rounded-full bg-muted-foreground"
        }
        style={{ width: `${Math.max((share / scale) * 100, share > 0 ? 2 : 0)}%` }}
      />
    </span>
  )
}

/**
 * Словами — то же, что показывают длины.
 *
 * Порог полуторакратный, а не любое расхождение: доли 20 % и 22 % отличаются
 * шумом выборки, и объявлять по ним «берёт чеком» значит сообщать о разнице,
 * которой нет.
 */
function verdict(money: number, count: number): string {
  if (count <= 0 || money <= 0) return "без продаж"
  const ratio = money / count
  if (ratio >= 1.5) return "берёт чеком"
  if (ratio <= 0.67) return "берёт числом"
  return "поровну"
}
