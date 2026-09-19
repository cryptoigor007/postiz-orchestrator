#!/bin/bash
# Мягко удаляет черновики Postiz старше 1 часа (DELETE через API в v1.47 сломан,
# а наши отмены/пересоздания оставляют черновики, которые мусорят календарь Postiz).
docker exec postiz-db psql -U postiz -d postiz -c \
  "UPDATE \"Post\" SET \"deletedAt\" = now() WHERE state='DRAFT' AND \"deletedAt\" IS NULL AND \"createdAt\" < now() - interval '1 hour';" \
  >/dev/null 2>&1
