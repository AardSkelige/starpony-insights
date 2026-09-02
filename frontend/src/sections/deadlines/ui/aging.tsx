import type { Deadlines } from "@/sections/deadlines/api"
import { BarList, type Bar } from "@/shared/components/bar-list"
import { CollapsibleNote } from "@/shared/components/collapsible-note"
import { formatMoney, formatShare } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

type Aging = Deadlines["aging"]

/**
 * Где застряли деньги — полосы по полкам возраста.
 *
 * **Полосы, а не столбики.** Это не изменение во времени, а сравнение
 * величин по четырём упорядоченным корзинам: вопрос к блоку один — «какая
 * из них тяжелее», и отвечает на него длина.
 *
 * **Все полосы одного тона.** Корзины упорядочены, и порядок уже показан
 * сверху вниз; красить их отдельными цветами значило бы закодировать
 * то же самое второй раз. Статусный цвет тоже не годится: сказать
 * «60 дней — это плохо» можно только зная срок оплаты, а его нет.
 *
 * Показывает то же множество, что таблица над ним: поиск сужает оба.
 */
export function Aging({ aging }: { aging: Aging }) {
  return (
    <CollapsibleNote title="Где застряли деньги" headline={headline(aging)}>
      <BarList bars={aging.map(toBar)} />
      <p className="mt-3 text-xs text-muted-foreground">
        Возраст — это сколько дней документ висит неоплаченным, а не просрочка:
        срок оплаты считается из отсрочки, а её нет ни у одного контрагента.
        Граница взята от жизни — столько обещает цикл выплаты площадки.
      </p>
    </CollapsibleNote>
  )
}

function toBar(shelf: Aging[number]): Bar {
  return {
    key: shelf.key,
    label: shelf.label,
    value: shelf.debt_kopecks,
    display: formatMoney(shelf.debt_kopecks),
    secondary: formatShare(shelf.share),
    hint: withPlural(shelf.count, "документ", "документа", "документов"),
  }
}

/**
 * Главное число — видно и в свёрнутом виде.
 *
 * Говорит про застарелое, а не про свежее: свежий долг решения не требует,
 * а блок открывают, чтобы понять, есть ли повод беспокоиться.
 */
function headline(aging: Aging): string {
  // Что считать застарелым и с какого дня — решает сервер и присылает
  // признаком у каждой полки. Свой список ключей здесь означал бы, что
  // про границу знают два места: сдвинь её на сервере, и фраза осталась бы
  // прежней, а складывать стала бы другие корзины — молча.
  const stale = aging
    .filter((shelf) => !shelf.fresh)
    .reduce((sum, shelf) => sum + shelf.debt_kopecks, 0)
  const whole = aging.reduce((sum, shelf) => sum + shelf.debt_kopecks, 0)
  // Потолок последней свежей полки — он же названная на экране граница.
  const boundary = aging.filter((shelf) => shelf.fresh).at(-1)?.up_to_days

  if (whole === 0) {
    return "долга нет"
  }
  if (stale === 0) {
    return `весь долг моложе ${withPlural(boundary ?? 0, "дня", "дней", "дней")}`
  }
  return `старше ${withPlural(boundary ?? 0, "дня", "дней", "дней")} — ${formatMoney(stale)} из ${formatMoney(whole)}`
}
