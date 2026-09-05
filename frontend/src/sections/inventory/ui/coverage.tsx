import type { InventoryCoverage } from "@/sections/inventory/api"
import { BarList, type Bar } from "@/shared/components/bar-list"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { Explain } from "@/shared/components/explain"
import { SummaryStat } from "@/shared/components/summary-stat"
import { formatDate } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * «Что не считали» — доля пересчитанного по папкам номенклатуры.
 *
 * Полосами, а не списком: «Производство/Тара — 0 из 27» в столбце чисел
 * не читается вовсе, а пустая дорожка рядом с полной видна мгновенно
 * (`CLAUDE.md` §8.0).
 *
 * Знаменатель — вся папка, а не пересчитанное: только так «сколько
 * из скольких» отвечает на вопрос. Папки без единого пересчёта остаются
 * в списке — они и есть ответ.
 */
export function Coverage({ coverage }: { coverage: InventoryCoverage }) {
  const bars: Bar[] = coverage.items.map((item) => ({
    key: item.folder,
    label: item.folder,
    value: item.counted_count,
    // «1 из 111» одним куском: разнеси числитель и знаменатель по двум
    // колонкам — и вторая строка ломается на три, потому что рядом с ней
    // стоит ещё и дата.
    display: `${item.counted_count} из ${item.products_count}`,
    // Дата, а не доля: «когда считали сырьё» — первый вопрос к группе,
    // и отвечать на него подсказкой по наведению значит не отвечать.
    // Одним словом: «не считали» переносится по пробелу и ломает строку
    // вдвое. «Никогда» — то же слово, что в колонке таблицы.
    secondary: item.last_moment === null ? "никогда" : formatDate(item.last_moment),
    hint:
      item.days_ago === null
        ? "не считали ни одной позиции"
        : `последний раз ${withPlural(item.last_days_ago ?? 0, "день", "дня", "дней")} назад; типично по позициям папки — ${withPlural(item.days_ago, "день", "дня", "дней")}`,
  }))

  return (
    <CollapsibleNote title="Что не считали" headline={headline(coverage)}>
      <div className="mb-4 grid gap-x-6 gap-y-3 sm:grid-cols-3">
        <SummaryStat
          label="Не считали ни разу"
          value={`${coverage.never_counted_count}`}
          note={`из ${withPlural(coverage.products_count, "позиции", "позиций", "позиций")} номенклатуры`}
          explain={
            <Explain>
              <b>Позиция, ни разу не попавшая в инвентаризацию.</b> Считаются
              товары и сырьё, не убранные в архив; услуги не считаются —
              их не пересчитывают. Пересчитанной позиция становится в тот
              момент, когда попала хоть в один документ, пусть и год назад.
            </Explain>
          }
        />
        <SummaryStat
          label="Пересчитали"
          value={`${coverage.counted_count} из ${coverage.products_count}`}
          note="хотя бы однажды"
          explain={
            <Explain>
              Сколько позиций попадало в инвентаризацию хоть раз. Это <b>не</b>{" "}
              «сколько сходится»: расхождения считаются отдельно, и они бывают
              только у пересчитанных.
            </Explain>
          }
        />
        <SummaryStat
          label="Дольше всех не открывали"
          value={coverage.oldest_folder || "—"}
          note={
            coverage.oldest_days_ago === null
              ? "пересчётов не было вовсе"
              : `${withPlural(coverage.oldest_days_ago, "день", "дня", "дней")} назад`
          }
          explain={
            <Explain>
              Папка с самой давней медианой пересчёта. <b>Медиана, а не
              среднее:</b> одна давняя позиция в папке из сорока сдвинула бы
              среднее на месяц и назвала бы забытой папку, которую считают
              регулярно. Папки, где не считали ничего, здесь не участвуют —
              им нечего мерить, и они видны полосой без заливки.
            </Explain>
          }
        />
      </div>

      <BarList bars={bars} wideLabels multilineLabels />
    </CollapsibleNote>
  )
}

/** Главное число — видно и в свёрнутом виде. */
function headline(coverage: InventoryCoverage): string {
  const never = coverage.never_counted_count
  if (never === 0) return `пересчитаны все ${coverage.products_count}`
  return `${withPlural(never, "позиция", "позиции", "позиций")} из ${coverage.products_count} не считали ни разу`
}
