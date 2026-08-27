/**
 * Какие номера показать: первую, последнюю, текущую с соседями.
 *
 * `null` — многоточие. Список номеров не растёт с числом страниц: при
 * шестидесяти шести наименованиях их две, но раздел приёмок легко даст
 * двадцать, и полоса из двадцати кнопок перестала бы помещаться.
 */
export function pagesToShow(page: number, pageCount: number): (number | null)[] {
  const shown = new Set([1, pageCount, page - 1, page, page + 1])
  const numbers = [...shown].filter((n) => n >= 1 && n <= pageCount).sort((a, b) => a - b)

  const result: (number | null)[] = []
  let previous = 0
  for (const number of numbers) {
    const gap = previous ? number - previous - 1 : 0
    // Пропущен ровно один номер — показываем его: многоточие занимает столько
    // же места, сколько цифра, но нажать на него нельзя.
    if (gap === 1) result.push(number - 1)
    else if (gap > 1) result.push(null)
    result.push(number)
    previous = number
  }
  return result
}
