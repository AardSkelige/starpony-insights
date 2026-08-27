import type { Page } from "@/shared/api/client"

/**
 * Раскладка меню: пункт без группы — верхний уровень, остальные по группам.
 *
 * Порядок задаёт сервер (реестр `api/access.py`), здесь он только сохраняется:
 * своя сортировка на фронтенде развела бы меню с админкой доступов, где
 * человек выдаёт права по тем же группам.
 */
export function splitNavigation(pages: Page[]): {
  top: Page[]
  groups: Array<{ label: string; pages: Page[] }>
} {
  const top: Page[] = []
  const groups: Array<{ label: string; pages: Page[] }> = []
  const index = new Map<string, number>()

  for (const page of pages) {
    if (!page.group) {
      top.push(page)
      continue
    }
    const at = index.get(page.group)
    if (at === undefined) {
      index.set(page.group, groups.length)
      groups.push({ label: page.group, pages: [page] })
    } else {
      groups[at].pages.push(page)
    }
  }

  return { top, groups }
}
