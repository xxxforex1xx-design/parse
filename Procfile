# Procfile — для Dokku/Heroku buildpack-режима.
# Если в репозитории есть Dockerfile, Dokku использует его и игнорирует
# этот файл. Оставлен как fallback: если кто-то решит собирать buildpack-ом
# (например, для быстрого эксперимента), нужно только удалить Dockerfile.
#
# web: процесс, который Dokku маршрутизирует через nginx → порт $PORT
# release: опциональные миграции/инициализация (сейчас не нужны)

web: uvicorn tools.web_app:app --host 0.0.0.0 --port ${PORT:-8000}
