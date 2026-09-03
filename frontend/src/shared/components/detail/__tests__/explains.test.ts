import { describe, expect, it } from "vitest"

/**
 * Каждый расчётный блок разбора объясняет себя — правило `DESIGN.md` §8.
 *
 * Проверяется по исходникам, а не рендером: разбор строки собран из блоков
 * без собственного состояния, и поднимать ради этого браузер дороже, чем
 * прочитать файл. Задача теста не в том, чтобы проверить разметку, — она
 * в том, чтобы **забытое объяснение падало**, а не жило до первого
 * замечания владельца.
 *
 * Так и вышло: значок стоял у «Где сидит расход» и отсутствовал у «Запаса»,
 * «Нормы расхода» и «Цены закупки». Рядом это читается не как «здесь
 * очевидно», а как «объяснений на странице нет» — и их перестают искать.
 *
 * Файлы читаются через `import.meta.glob` — это Vite, а не Node: тест
 * остаётся в той же среде, что и остальные, и не требует типов `node`.
 */
const UI = import.meta.glob("../../../../sections/*/ui/*.tsx", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>

const SECTION_SOURCE = readSectionSource(UI)

/** Разделы разбора, которые показывают посчитанное, а не взятое из учёта. */
const COMPUTED: Record<string, string[]> = {
  "shipments-materials": ["Норма расхода", "Где сидит расход", "Цена закупки"],
  "supplies-materials": ["Цена", "Закупки", "У кого дешевле"],
  "shipments-products": ["Цена", "Когда продавали", "Кому продавали", "Ушло без оплаты"],
  suppliers: ["Ритм поставок", "Срок поставки"],
  // Оба блока разбора расчётные: в первом долг посчитан вычитанием
  // и без отгрузок по комиссии, во втором — как раз они.
  deadlines: ["Неоплаченные документы", "Товар на реализации"],
  // Три блока разбора и три карточки над таблицей: последние живут в том же
  // `ui/` и объясняются по тому же правилу — число без формулы незакрыто.
  // Ведущий блок разбора расчётный целиком, а «Что осталось за пределами
  // расчёта» объясняет себестоимость отданного даром: количество наше,
  // цена единицы — средняя за период из отчёта.
  profitability: ["Из чего сложилась маржа", "Что осталось за пределами расчёта"],
  channels: [
    "Кто покупает",
    "Что покупают",
    "Как рос канал",
    "Кому уходят деньги",
    "Деньги против отгрузок",
    "Как менялось",
  ],
}

/**
 * Заголовок блока и его окрестность — до открывающей скобки компонента.
 *
 * Ловит обе формы: буквальную (`title="Запас"`) и выбранную выражением
 * (`title={free ? "Ушло без оплаты" : "Кому продавали"}`) — один компонент
 * рисует оба блока, когда у них общий вид и разный вопрос.
 *
 * Окно широкое намеренно: у блока с двумя вариантами объяснения между
 * заголовком и `explain=` помещается вся развилка.
 */
function titleRe(title: string): RegExp {
  return new RegExp(
    `title=(?:"${title}"|\\{[^}]*"${title}"[^}]*\\})[\\s\\S]{0,900}?>`,
    "g"
  )
}

/** Все `.tsx` каждого раздела одной строкой: блоки разложены по файлам. */
function readSectionSource(files: Record<string, string>): Record<string, string> {
  const bySection: Record<string, string> = {}
  for (const [path, source] of Object.entries(files)) {
    const section = path.match(/sections\/([^/]+)\/ui\//)?.[1]
    if (!section) continue
    bySection[section] = (bySection[section] ?? "") + "\n" + source
  }
  return bySection
}

describe.each(Object.entries(COMPUTED))(
  "разбор строки «%s» объясняет свои числа",
  (section, titles) => {
    it("исходники раздела прочитаны", () => {
      // Без этой проверки переезд файлов превратил бы весь набор
      // в зелёный тест, не проверяющий ничего.
      expect(SECTION_SOURCE[section], `не найдены файлы ${section}/ui`).toBeTruthy()
    })

    it.each(titles)("у раздела «%s» есть значок объяснения", (title) => {
      // Вхождений у заголовка несколько: свои `Section` рисуют состояния
      // «едет» и «не доехало», и объяснять там нечего. Достаточно, чтобы
      // объяснение было хотя бы у одного — того, что показывает числа.
      const blocks = [
        ...(SECTION_SOURCE[section] ?? "").matchAll(titleRe(title)),
      ]

      expect(
        blocks.length,
        `раздел «${title}» не найден в ${section}/ui`
      ).toBeGreaterThan(0)
      expect(
        blocks.some((block) => block[0].includes("explain=")),
        `у раздела «${title}» нет объяснения — DESIGN §8`
      ).toBe(true)
    })
  }
)

/**
 * Расчётные блоки общего слоя.
 *
 * Проверяются отдельно от разделов: «Запас» переехал в `shared/`, когда
 * понадобился второму разделу, и выпал бы из проверки по разделам молча —
 * а это ровно тот блок, ради которого страницу открывают.
 */
const SHARED_COMPUTED = ["Запас"]

const SHARED_SOURCE = Object.values(
  import.meta.glob("../*.tsx", {
    query: "?raw",
    import: "default",
    eager: true,
  }) as Record<string, string>
).join("\n")

describe("расчётные блоки общего слоя объясняют себя", () => {
  it.each(SHARED_COMPUTED)("у раздела «%s» есть значок объяснения", (title) => {
    const blocks = [
      ...SHARED_SOURCE.matchAll(titleRe(title)),
    ]

    expect(
      blocks.length,
      `раздел «${title}» не найден в shared/components/detail`
    ).toBeGreaterThan(0)
    expect(
      blocks.some((block) => block[0].includes("explain=")),
      `у раздела «${title}» нет объяснения — DESIGN §8`
    ).toBe(true)
  })
})

describe("значок объяснения не исчезает за вкладкой", () => {
  it("`Section` рисует explain и в кратком виде", () => {
    // На телефоне таблица показывается карточками, подсказки у заголовков
    // колонок недостижимы вовсе, и разбор строки остаётся единственным
    // местом, где формулу можно посмотреть.
    const source = Object.entries(
      import.meta.glob("../index.tsx", {
        query: "?raw",
        import: "default",
        eager: true,
      }) as Record<string, string>
    )[0]?.[1]

    expect(source, "не найден shared/components/detail/index.tsx").toBeTruthy()

    // Режем ровно краткую ветку: до `) : (`. Срез до `{note ?` захватывал
    // и полную ветку, где `explain` есть всегда, — и проверка проходила
    // вхолостую при пустой краткой.
    const start = source!.indexOf("{bare ? (")
    const bareBranch = source!.slice(start, source!.indexOf(") : (", start))

    expect(bareBranch, "объяснение пропадает за вкладкой").toContain("{explain}")
  })
})
