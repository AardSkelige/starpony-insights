import { Link } from "react-router"

import type { HomeMisplaced, HomeListRow } from "@/sections/home/api"
import { misplacedRemark, jokeOfTheDay, NOTHING_TO_DO } from "@/sections/home/remarks"
import { FullList } from "@/sections/home/ui/full-list"
import { Tile } from "@/sections/home/ui/tile"
import { BarList } from "@/shared/components/bar-list"
import { Explain } from "@/shared/components/explain"
import { formatEstimate } from "@/sections/home/format"
import { withPlural } from "@/shared/lib/plural"
import { Button } from "@/shared/ui/button"

/**
 * Ведущая плитка: «Деньги лежат не там».
 *
 * **Единственное число страницы, которого нет в учёте ни в каком виде.**
 * МойСклад показывает остатки и продажи по отдельности; чего он не говорит —
 * что одно связано с другим: полмиллиона лежит в сырье, из которого
 * не сварили то, что кончилось.
 *
 * **Упущенное — оценка, и подпись держит эту разницу.** Мы не знаем,
 * сколько бы продали; мы знаем темп, с которым продавали до того, как товар
 * кончился. Поэтому «столько стоит простой», а не «столько мы потеряли».
 */
export function MisplacedTile({ data }: { data: HomeMisplaced }) {
  const nothing = !data.lost_positions && !data.frozen_positions

  if (nothing) {
    // Пустой блок — не пустое состояние, а хорошая новость (`DESIGN.md` §9),
    // и единственное место страницы, где уместна крупная шутка.
    return (
      <Tile title="Деньги лежат не там" window="Состояние на сейчас" className="lg:col-span-2">
        <div className="flex flex-col gap-1.5 py-1">
          <span className="text-xl font-semibold tracking-tight">{NOTHING_TO_DO.head}</span>
          <span className="text-sm text-muted-foreground">{jokeOfTheDay()}</span>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Ни одной позиции без остатка при живом спросе. Сырьё расходуется.
        </p>
      </Tile>
    )
  }

  return (
    <Tile
      title="Деньги лежат не там"
      tone="warning"
      window={`Спрос за ${data.demand_days} дней, расход сырья за ${data.material_days}`}
      windowNote="окна длиннее месяца: за месяц не отличить «кончилось» от «не продавалось»"
      explain={
        <Explain>
          Упущенное — темп продаж до того, как товар кончился, умноженный
          на цену продажи и на 30 дней. Это оценка простоя, а не потеря:
          сколько бы продали, мы не знаем. Заморожено — остаток × себестоимость
          по сырью, которого при нынешнем расходе хватит больше чем на год
          либо которое не расходовалось вовсе.
        </Explain>
      }
      className="lg:col-span-2"
      remark={misplacedRemark(data) ?? undefined}
    >
      <div className="mb-4 flex flex-wrap gap-x-10 gap-y-4">
        <div className="min-w-0">
          <div className="text-2xl font-semibold tracking-tight text-warning tabular-nums sm:text-3xl">
            {formatEstimate(data.lost_kopecks)}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">упускаем в месяц</div>
          <div className="text-xs text-muted-foreground">
            {withPlural(data.lost_positions, "позиция кончилась", "позиции кончились", "позиций кончилось")}, спрос есть
          </div>
        </div>
        <div className="min-w-0">
          <div className="text-2xl font-semibold tracking-tight tabular-nums sm:text-3xl">
            {formatEstimate(data.frozen_kopecks)}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">заморожено в сырье</div>
          <div className="text-xs text-muted-foreground">
            {/* Обе величины — деньги. Раньше здесь стояло «121 из 468 900 ₽»:
                счётчик позиций против денежного итога склада, и читалось это
                как ошибка данных. Сравнивать можно только сравнимое. */}
            из {formatEstimate(data.stock_kopecks)} на складе ·{" "}
            {withPlural(data.frozen_positions, "позиция", "позиции", "позиций")}
          </div>
        </div>
      </div>

      {data.to_brew.length ? (
        <>
          {/* Фраза «сырьё на первые позиции есть — партию можно собрать
              сегодня» стояла здесь статикой из макета и оказалась неправдой:
              проверка показала, что ни на одну из трёх сырья не хватает —
              воды нужно 21 600 при остатке 8 314. Утверждение, которого
              никто не считал, — это запрет `DESIGN.md` §15 «не выдумывать
              данные»; хватает ли сырья, знает «Расчёт производства»,
              и кнопка ведёт именно туда. */}
          <p className="mb-3 rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
            Деньги вложены в то, из чего не сварили.{" "}
            <span className="font-medium text-foreground">
              Вот на чём теряем больше всего, пока этого нет на складе.
            </span>
          </p>
          <BarList bars={toBars(data.to_brew, "в день")} wideLabels multilineLabels />
        </>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" render={<Link to="/production" viewTransition />}>
          Собрать партию
        </Button>
        <FullList
          label={`Что кончилось — все ${data.lost_positions}`}
          title="Товары, которых нет на складе"
          subtitle={`Спрос за ${data.demand_days} дней · рядом — сколько стоит простой в месяц`}
          rows={data.lost_all}
          total={data.lost_positions}
        />
      </div>
    </Tile>
  )
}

/** Что лежит без движения — отдельной плиткой: у неё свой вопрос. */
export function LyingStillTile({ data }: { data: HomeMisplaced }) {
  if (!data.lying_still.length) return null

  return (
    <Tile
      title="Что лежит без движения"
      window={`Расход за ${data.material_days} дней`}
      windowNote="сырьё, тара и этикетки — хозтовары сюда не входят"
      remark={`Всего ${formatEstimate(data.frozen_kopecks)} — это ${Math.round((data.frozen_kopecks / Math.max(data.stock_kopecks, 1)) * 100)} % склада. Правнуки оценят запасливость.`}
    >
      <BarList bars={toBars(data.lying_still)} wideLabels multilineLabels />
      <div className="mt-3">
        <FullList
          label={`Показать все ${data.frozen_positions}`}
          title="Сырьё, которое не двигается"
          subtitle={`Расход за ${data.material_days} дней · хватит больше чем на год либо не расходуется вовсе`}
          rows={data.frozen_all}
          total={data.frozen_positions}
        />
      </div>
    </Tile>
  )
}

function toBars(rows: HomeListRow[], suffix = "") {
  return rows.map((row) => ({
    key: row.name,
    label: row.name,
    value: row.value,
    display: formatEstimate(row.value) + (suffix ? ` ${suffix}` : ""),
    hint: row.note,
  }))
}
