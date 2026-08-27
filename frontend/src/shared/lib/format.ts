/**
 * Приведение чисел учёта к виду, который читает человек.
 *
 * Всё, что приходит с сервера, приходит в единицах хранения: деньги — целыми
 * копейками, удельные величины и количества — строками Decimal. Рубли,
 * проценты и разделители разрядов появляются только здесь: перевести их
 * раньше значит потерять знаки там, где они решают, сойдётся ли с учётом.
 */

const RU = "ru-RU"

/** Неразрывный пробел перед знаком рубля: «231 530,38 ₽» не переносится. */
const NBSP = " "

const money = new Intl.NumberFormat(RU, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const percent = new Intl.NumberFormat(RU, {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

/** Деньги: из целых копеек в рубли. Копейки — целое число, дроби в них не бывает. */
export function formatMoney(kopecks: number): string {
  return `${money.format(kopecks / 100)}${NBSP}₽`
}

/**
 * Цена за единицу: приходит строкой Decimal в копейках и бывает дробной.
 *
 * Показывается двумя знаками, но округляется только на экране — в расчётах
 * участвует то, что пришло: у 150 позиций из 255 себестоимость дробная,
 * и округление до копейки даёт 65 копеек на тысячу единиц.
 */
export function formatUnitPrice(kopecks: string | null): string {
  if (kopecks === null) return "—"
  return `${money.format(Number(kopecks) / 100)}${NBSP}₽`
}

/**
 * Количество: строка Decimal с тремя знаками.
 *
 * Хвост из нулей убирается — «430» вместо «430.000». Дробная часть
 * сохраняется там, где она есть: килограммы и граммы сырья дробные,
 * и «0,5 кг», показанные как «1 кг», расходятся с учётом вдвое.
 */
export function formatQuantity(value: string, uom?: string): string {
  const number = Number(value)
  const text = new Intl.NumberFormat(RU, { maximumFractionDigits: 3 }).format(number)
  return uom ? `${text}${NBSP}${uom}` : text
}

/** Доля единицы в проценты: 0.1894 → «18,9 %». */
export function formatShare(share: string | null): string {
  if (share === null) return "—"
  return `${percent.format(Number(share) * 100)}${NBSP}%`
}

/**
 * Отметка свежести данных — «данные на 14:32».
 *
 * Если синхронизация прошла не сегодня, показывается и дата: иначе «14:32»
 * у вчерашних данных читается как «только что», а это ровно та ошибка,
 * ради которой отметка и существует.
 */
export function formatSyncedAt(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "данные ещё не загружались"

  const moment = new Date(iso)
  const time = moment.toLocaleTimeString(RU, { hour: "2-digit", minute: "2-digit" })

  const sameDay =
    moment.getFullYear() === now.getFullYear() &&
    moment.getMonth() === now.getMonth() &&
    moment.getDate() === now.getDate()

  if (sameDay) return `данные на ${time}`

  const date = moment.toLocaleDateString(RU, { day: "2-digit", month: "2-digit" })
  return `данные на ${date}, ${time}`
}

/** Дата для полей периода: «01.04.2026». */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(RU, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}
