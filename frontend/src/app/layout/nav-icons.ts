import {
  Boxes,
  CalendarClock,
  ClipboardList,
  Factory,
  LayoutDashboard,
  PackageSearch,
  Radio,
  Truck,
  Wallet,
  Warehouse,
  type LucideIcon,
} from "lucide-react"

/**
 * Иконка на каждый пункт меню.
 *
 * Держится на фронтенде, а не приходит с сервера: это чисто визуальное
 * решение, реестру страниц в `api/access.py` о нём знать незачем. Ключи —
 * оттуда же, и промах ловится проверкой ниже, а не пустым местом в рельсе.
 *
 * Иконка обязательна каждому пункту: в свёрнутом сайдбаре показывать больше
 * нечего (DESIGN.md §4).
 */
export const NAV_ICONS: Record<string, LucideIcon> = {
  home: LayoutDashboard,
  "shipments-products": Truck,
  "shipments-materials": PackageSearch,
  "supplies-materials": Warehouse,
  suppliers: Boxes,
  production: Factory,
  inventory: ClipboardList,
  deadlines: CalendarClock,
  profitability: Wallet,
  channels: Radio,
}

/** Запасная иконка: пункт без своей всё равно должен быть виден в рельсе. */
export const FALLBACK_ICON = ClipboardList
