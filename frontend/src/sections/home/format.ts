import type { HomeFigure } from "@/sections/home/api"
import { formatMoney, NBSP } from "@/shared/lib/format"

/**
 * Как показывать значение — зависит от того, что это за величина.
 *
 * Проценты приходят в сотых долях (8689 — это 86,89 %) по той же причине,
 * по которой деньги приходят в копейках: целое переживает JSON без потерь,
 * а округляется оно ровно один раз — здесь.
 */
export function formatFigure(value: number, unit: HomeFigure["unit"]): string {
  if (unit === "money") return formatMoney(value)
  if (unit === "percent") return `${(value / 100).toFixed(1).replace(".", ",")} %`
  return value.toLocaleString("ru-RU")
}

/**
 * Оценка в рублях, без копеек.
 *
 * **Копейки в оценке — ложная точность.** «Упускаем 169 649,97 ₽» обещает
 * точность до копейки там, где число получено умножением среднего темпа
 * продаж на цену: мы не знаем, сколько бы продали, — мы знаем, с какой
 * скоростью продавали. Две цифры после запятой утверждают обратное.
 *
 * Точные суммы — выручка каналов, маржа, отгрузки — по-прежнему идут через
 * `formatMoney` с копейками: они сходятся с числами других страниц,
 * и округление здесь развело бы главную с «Каналами продаж».
 */
export function formatEstimate(kopecks: number): string {
  return `${Math.round(kopecks / 100).toLocaleString("ru-RU")}${NBSP}₽`
}
