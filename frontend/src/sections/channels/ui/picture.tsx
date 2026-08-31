import type { Channels } from "@/sections/channels/api"
import { DynamicsCard } from "@/sections/channels/ui/dynamics-card"
import { PaceCard } from "@/sections/channels/ui/pace-card"
import { RevenueCard } from "@/sections/channels/ui/revenue-card"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { formatMoney, formatShare } from "@/shared/lib/format"

/**
 * Картина продаж — три графика одним сворачиваемым блоком под таблицей.
 *
 * **Под таблицей, а не над ней, и свёрнуто.** Сначала графики стояли сверху:
 * они отвечают быстрее таблицы, и казалось правильным дать ответ первым.
 * Владелец поправил 30.08, и довод сильнее: **все страницы обязаны
 * открываться одинаково** — шапка, фильтры, таблица. Полэкрана графиков
 * перед строками ломают привычку, наработанную на четырёх других разделах,
 * и к каждой странице приходится привыкать заново.
 *
 * **В свёрнутом виде блок остаётся осмысленным:** заголовок называет
 * крупнейший канал и его долю — то самое, ради чего блок раскрывают.
 *
 * Раскладка внутри: ряд по времени во всю ширину — ему ширина нужнее всего,
 * двадцать два столбика в трети экрана сливаются в гребёнку. Два списка
 * под ним рядом: у них одинаковое число строк, поэтому и высота одна.
 * Первая версия ставила все три карточки в ряд, и средняя вымахивала вдвое
 * выше боковых, оставляя по краям пустоту.
 */
export function Picture({ data }: { data: Channels }) {
  if (data.standings.length === 0) return null

  const leader = data.standings[0]

  return (
    <CollapsibleNote
      title="Картина продаж"
      headline={`${leader.name} — ${formatShare(leader.revenue_share)} выручки · ${formatMoney(data.coverage.revenue_kopecks)} за период`}
    >
      <div className="flex flex-col gap-4">
        <DynamicsCard dynamics={data.dynamics} />
        <div className="grid gap-4 lg:grid-cols-2">
          <RevenueCard standings={data.standings} />
          <PaceCard standings={data.standings} />
        </div>
      </div>
    </CollapsibleNote>
  )
}
