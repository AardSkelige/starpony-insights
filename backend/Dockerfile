FROM python:3.12-slim

# PYTHONUNBUFFERED: без него логи Django оседают в буфере и не доходят
# до docker logs, пока процесс не завершится, — а нужны они именно тогда,
# когда он не завершается.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Зависимости отдельным слоем: правка кода не пересобирает установку пакетов.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Приложение работает не от root: если процесс скомпрометирован, у него
# не должно быть прав менять собственный код и системные файлы.
RUN useradd --system --create-home app && chown -R app:app /app
USER app

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
