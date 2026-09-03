import type { components } from "@/shared/api/schema"
import { formatShare } from "@/shared/lib/format"

export type ConsignmentShare = components["schemas"]["ConsignmentShare"]

/**
 * Подпись доли реализации у полосы или в строке.
 *
 * Всегда рядом с числом, а не только при перекраске: **цветом в одиночку
 * статус не передаётся** (`DESIGN.md` §1). Цвет отвечает на «пора ли
 * пересмотреть вывод», подпись — на «насколько».
 *
 * `null` там, где реализации нет: подпись «0 % на реализации» у восьми
 * каналов из девяти — шум, за которым не заметят единственный настоящий.
 */
export function consignmentHint(share: ConsignmentShare): string | null {
  if (share.consignment_kopecks <= 0) return null
  return `${formatShare(share.fraction)} на реализации — отгружено, ещё не продано`
}
