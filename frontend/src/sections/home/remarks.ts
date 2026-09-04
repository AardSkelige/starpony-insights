import type { Home } from "@/sections/home/api"
import { formatMoney } from "@/shared/lib/format"
import { withPlural } from "@/shared/lib/plural"

/**
 * Замечания внизу плиток.
 *
 * **Каждое опирается на число из своей же плитки** — иначе это украшение,
 * а на странице решений украшение превращается в сор, за которым перестают
 * читать и остальное. Отсюда же правило «одно на плитку»: два подряд
 * читаются как разговор, а не как подпись.
 *
 * Живут отдельным файлом, а не внутри компонентов, по двум причинам. Первая:
 * их правят целым набором — тон подбирается сравнением фраз друг с другом,
 * а не по одной. Вторая: у них есть условие — замечание, верное при пустом
 * складе, становится неуместным, когда всё в порядке, и это видно только
 * когда они лежат рядом.
 *
 * `null` — законный ответ: плитке без замечания молчание идёт больше,
 * чем натянутая шутка.
 */

/** Заголовок и фраза для пустого состояния ведущей плитки. */
export const NOTHING_TO_DO = {
  head: "Всё на своих местах",
  /**
   * Крутятся по дате, а не случайно: перезагрузка страницы не должна менять
   * шутку — это выглядит как подёргивание интерфейса. Один день — одна фраза.
   *
   * Ни одна не склоняет «МойСклад»: это название, а не слово. То же правило,
   * что у фраз ожидания синхронизации (`shared/api/sync.ts`).
   */
  jokes: [
    "Разбирать нечего. Можно идти варить кондиционер.",
    "Пусто, как флакон после розлива.",
    "Ни одной задачи. Даже отдушка Бубль-Гам никого не беспокоит.",
    "Склад сходится, долгов нет, цены на месте. Подозрительно.",
    "Все проверки прошли. Запишите этот день.",
  ],
}

export function jokeOfTheDay(now: Date = new Date()): string {
  const day = Math.floor(now.getTime() / 86_400_000)
  return NOTHING_TO_DO.jokes[day % NOTHING_TO_DO.jokes.length]
}

export function misplacedRemark(data: NonNullable<Home["misplaced"]>): string | null {
  if (!data.lost_positions && !data.frozen_positions) return null
  return (
    `${withPlural(data.lost_positions, "позиция кончилась", "позиции кончились", "позиций кончилось")}, ` +
    `${withPlural(data.frozen_positions, "лежит", "лежат", "лежат")} без движения. ` +
    `Деньги в шампуне есть — просто не в том шампуне.`
  )
}

export function signalsRemark(signals: Home["signals"]): string {
  const clean = signals.filter((signal) => signal.count === 0).length
  if (clean === signals.length) {
    return "Все проверки чисты. Седьмую заведём, когда эти начнут что-нибудь находить."
  }
  return `${withPlural(signals.length, "проверка", "проверки", "проверок")}. Седьмую заведём, когда эти перестанут что-нибудь находить.`
}

export function pulseRemark(data: NonNullable<Home["pulse"]>): string | null {
  const receipt = data.shipped.find((figure) => figure.key === "receipt")
  if (!receipt || receipt.change === null) return null

  const change = Number(receipt.change)
  if (change >= 0) return null
  return (
    `Средний чек упал на ${Math.abs(change).toFixed(0)} % не от бедности: ` +
    `маркетплейсы берут по одной баночке, а до них брали ящиками.`
  )
}

export function marginsRemark(margins: NonNullable<Home["margins"]>): string | null {
  const worst = margins.at(-1)
  // Нижняя граница обязательна: при отрицательной марже фраза становилась
  // «принёс −1 234 ₽ прибыли — по −12 ₽ с бутылки». Убыточные позиции
  // в проекте реальны, под них заведён отдельный сигнал `at-a-loss`,
  // и шутить про прибыль там нечего.
  if (!worst || worst.margin >= 2000 || worst.margin <= 0) return null

  // Нулевое количество даёт `Infinity` и «∞ ₽ с бутылки». В выборку такие
  // строки попасть не должны — маржа считается от выручки, — но проверка
  // здесь дешевле разбирательства, откуда на экране взялась бесконечность.
  const quantity = Number(worst.quantity)
  if (!quantity) return null

  const profit = (worst.revenue_kopecks * worst.margin) / 10_000
  const each = profit / quantity
  return (
    `${worst.name} за ${withPlural(Math.round(Number(worst.quantity)), "штуку", "штуки", "штук")} ` +
    `принёс ${formatMoney(Math.round(profit))} прибыли — по ${formatMoney(Math.round(each))} с бутылки. ` +
    `За такие деньги её приятнее подарить.`
  )
}

export function changesRemark(): string {
  return (
    "Вверх обычно идут пятисотки, вниз — пятилитровки. " +
    "Пятилитровку берут раз в полгода, каждый месяц расти она и не обязана."
  )
}

/**
 * Замечание владельца: сырьё чаще всего покупается на личные деньги Яны.
 * Держится ровно до того дня, когда каналы начнут это покрывать, — и тогда
 * фраза перестанет быть шуткой сама собой.
 */
export function channelsRemark(): string {
  return (
    "Яны в списке нет. А ведь сырьё чаще всего покупается на её деньги — " +
    "когда-нибудь это прекратится."
  )
}
