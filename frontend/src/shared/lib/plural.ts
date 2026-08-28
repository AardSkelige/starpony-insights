/**
 * Склонение существительного при числе.
 *
 * «Ещё 1 изделие», «ещё 2 изделия», «ещё 39 изделий» — иначе интерфейс
 * говорит «39 изделие», и это первое, что замечают в готовой странице.
 */
export function plural(count: number, one: string, few: string, many: string): string {
  const tens = count % 100
  // Одиннадцать–четырнадцать — исключение: они кончаются на 1–4,
  // но склоняются как «много».
  if (tens >= 11 && tens <= 14) return many

  switch (count % 10) {
    case 1:
      return one
    case 2:
    case 3:
    case 4:
      return few
    default:
      return many
  }
}

/** Число вместе со словом: «39 изделий». */
export function withPlural(
  count: number,
  one: string,
  few: string,
  many: string
): string {
  return `${count} ${plural(count, one, few, many)}`
}
