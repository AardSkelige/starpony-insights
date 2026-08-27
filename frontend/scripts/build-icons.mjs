// Сборка фавикона и иконок из одного контура — src/shared/components/logo.tsx.
//
// Запускается руками (`npm run icons`), а не при сборке: логотип меняется раз
// в жизни, а требовать librsvg на каждом `npm run build` и в CI — плата,
// несоразмерная поводу. Результат лежит в public/ и коммитится.
//
// Нужен librsvg: brew install librsvg
import { execFileSync } from "node:child_process"
import { readFileSync, writeFileSync } from "node:fs"
import path from "node:path"

const publicDir = path.resolve(import.meta.dirname, "../public")
const logoSource = path.resolve(
  import.meta.dirname,
  "../src/shared/components/logo.tsx"
)

// Токены темы из src/index.css: --primary светлой темы и --foreground тёмной.
// Здесь они разворачиваются в hex — PNG не умеет ссылаться на переменную CSS.
const INK_LIGHT = "#171717"
const INK_DARK = "#fafafa"
// --background тёмной темы: цвет заставки, на которой система показывает
// иконку при запуске. Тёмный при любой теме приложения — подложка иконки
// тоже тёмная, и заставка читается как её продолжение.
const SPLASH = "#0a0a0a"

const contour = readFileSync(logoSource, "utf8").match(/"(M[^"]+)"/)?.[1]
if (!contour) {
  throw new Error(`Не нашёл контур логотипа в ${logoSource}`)
}

// Фавикон — единственная иконка без подложки: показывается на фоне вкладки,
// и своя подложка спорила бы с ним. Тему выбирает сам файл: он живёт вне
// документа, класс .dark на <html> до него не достаёт.
writeFileSync(
  path.join(publicDir, "favicon.svg"),
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500">
  <title>StarPony Insights</title>
  <style>
    path { fill: ${INK_LIGHT} }
    @media (prefers-color-scheme: dark) { path { fill: ${INK_DARK} } }
  </style>
  <path d="${contour}"/>
</svg>
`
)

// Остальные иконки — с подложкой, потому что тему выбрать не могут: iOS и
// Android рисуют ярлык один раз, независимо от темы телефона. Подложка та же,
// что у плашки логотипа в интерфейсе, — тёмная, контур светлый.
function png(name, size, { scale, radius = 0 }) {
  const offset = (500 * (1 - scale)) / 2
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500">
  <rect width="500" height="500" rx="${radius}" fill="${INK_LIGHT}"/>
  <g transform="translate(${offset} ${offset}) scale(${scale})" fill="${INK_DARK}">
    <path d="${contour}"/>
  </g>
</svg>
`
  execFileSync(
    "rsvg-convert",
    ["-w", String(size), "-h", String(size), "-o", path.join(publicDir, name)],
    {
      input: svg,
    }
  )
  console.log(`${name} — ${size}×${size}`)
}

// Запасной фавикон для браузеров без поддержки SVG в rel="icon".
// Скруглён: у него нет маски системы, которая сделала бы это за нас.
png("favicon-96.png", 96, { scale: 0.78, radius: 110 })

// iOS: ярлык на домашнем экране. Только PNG и только непрозрачный —
// прозрачность iOS заливает чёрным.
png("apple-touch-icon.png", 180, { scale: 0.74 })

// Android и десктопные PWA — через манифест.
png("icon-192.png", 192, { scale: 0.78 })
png("icon-512.png", 512, { scale: 0.78 })

// Maskable: система обрезает иконку своей формой, гарантированно видна только
// центральная окружность в 80% ширины. Контур ужат, чтобы в неё уместиться.
png("icon-maskable-512.png", 512, { scale: 0.56 })

// Манифест собирается здесь же — иначе цвета подложки жили бы в двух файлах
// и разъехались бы при первой же правке.
//
// Имя manifest.json, а не общепринятое site.webmanifest: расширения
// .webmanifest нет в таблицах типов ни у Caddy, ни у nginx, и файл уходит
// с типом text/plain. У .json тип известен всем.
writeFileSync(
  path.join(publicDir, "manifest.json"),
  JSON.stringify(
    {
      name: "StarPony Insights",
      // Подпись под иконкой на домашнем экране: длиннее ~12 знаков система
      // обрежет многоточием, а «пони» и так сказано самой иконкой.
      short_name: "Insights",
      lang: "ru",
      start_url: "/",
      scope: "/",
      display: "standalone",
      background_color: SPLASH,
      theme_color: SPLASH,
      icons: [
        { src: "/favicon.svg", type: "image/svg+xml", sizes: "any" },
        { src: "/icon-192.png", type: "image/png", sizes: "192x192" },
        { src: "/icon-512.png", type: "image/png", sizes: "512x512" },
        {
          src: "/icon-maskable-512.png",
          type: "image/png",
          sizes: "512x512",
          purpose: "maskable",
        },
      ],
    },
    null,
    2
  ) + "\n"
)
console.log("manifest.json")
