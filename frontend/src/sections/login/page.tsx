import * as React from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Lock } from "lucide-react"

import { ThemeSwitch } from "@/app/layout/theme-switch"
import { ApiError } from "@/shared/api/client"
import { sessionKeys, signIn } from "@/shared/auth/session"
import { Button } from "@/shared/ui/button"
import { Field, FieldError, FieldGroup, FieldLabel } from "@/shared/ui/field"
import { Input } from "@/shared/ui/input"

export function LoginPage() {
  const [username, setUsername] = React.useState("")
  const [password, setPassword] = React.useState("")
  const queryClient = useQueryClient()

  const login = useMutation({
    mutationFn: () => signIn(username, password),
    onSuccess: (profile) => {
      // Профиль кладётся в кэш сразу: иначе оболочка после перехода запросит
      // его заново и покажет пустой каркас на время лишнего запроса.
      // Уводит со страницы не мутация, а сама страница — там переход один
      // и с анимацией.
      queryClient.setQueryData(sessionKeys.profile, profile)
    },
  })

  const errorText =
    login.error instanceof ApiError
      ? login.error.message
      : login.error
        ? "Сервер недоступен. Попробуйте ещё раз."
        : null

  return (
    <div className="relative grid min-h-svh lg:grid-cols-2">
      {/* Переключатель доступен до входа: иначе человек с тёмной системной темой
          встречает белую вспышку и ничего не может с ней сделать. */}
      <ThemeSwitch className="absolute top-4 right-4 z-10" />

      {/* Панель контрастна теме: тёмная при светлой и наоборот. Так экран
          входа читается как обложка, а не как ещё одна страница приложения. */}
      <aside className="hidden flex-col justify-between bg-foreground p-10 text-background lg:flex">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-background text-sm font-semibold text-foreground">
            SP
          </div>
          <span className="font-semibold">StarPony Insights</span>
        </div>

        <p className="max-w-sm text-lg leading-relaxed text-balance">
          Отгрузки, материалы, сроки оплаты и себестоимость — в одном месте,
          с объяснением каждой цифры.
        </p>
      </aside>

      <main className="flex items-center justify-center p-6">
        <form
          className="flex w-full max-w-75 flex-col gap-5"
          onSubmit={(event) => {
            event.preventDefault()
            login.mutate()
          }}
        >
          <div className="flex flex-col gap-1">
            <h1 className="text-xl font-semibold tracking-tight">Вход</h1>
            <p className="text-sm text-muted-foreground">Введите логин и пароль</p>
          </div>

          <FieldGroup>
            <Field data-invalid={errorText ? true : undefined}>
              <FieldLabel htmlFor="username">Логин</FieldLabel>
              <Input
                id="username"
                autoComplete="username"
                autoFocus
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                aria-invalid={errorText ? true : undefined}
              />
            </Field>

            <Field data-invalid={errorText ? true : undefined}>
              <FieldLabel htmlFor="password">Пароль</FieldLabel>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-invalid={errorText ? true : undefined}
              />
              {errorText ? <FieldError>{errorText}</FieldError> : null}
            </Field>
          </FieldGroup>

          <Button type="submit" disabled={login.isPending}>
            {login.isPending ? "Проверяем…" : "Войти"}
          </Button>

          <p className="flex items-start gap-2 rounded-lg bg-muted p-3 text-xs text-muted-foreground">
            <Lock className="mt-px size-3.5 shrink-0" />
            <span>
              Доступ к разделам выдаётся отдельно — вы увидите только своё.
            </span>
          </p>
        </form>
      </main>
    </div>
  )
}
