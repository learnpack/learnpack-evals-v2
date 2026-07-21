# ADR-0003 — Postgres (Neon) como store y events-first sobre tabla de eventos

**Estado:** aceptada · **Fecha:** 2026-07 · **Contexto:** todo el backend

## Contexto
El MVP necesita persistencia. Se descartó Google Sheets (no es DB real, querying/concurrencia
pobres, sin pgvector, incómodo detrás de repository-ports). El stack objetivo ya usa
Postgres/pgvector, y se quiere sostener el enfoque events-first sin montar un bus real todavía.

## Decisión
- **Neon (Postgres serverless, pgvector incluido)** como store, detrás de repository-ports. La DB
  es un adapter; la lógica vive en el dominio.
- **Events-first realizado como outbox en Postgres:** cada use case escribe el agregado y hace
  `INSERT` en una tabla `events` **en la misma transacción**; tras el commit, un **dispatcher
  in-process** entrega el evento a las policies suscritas (síncrono en MVP).
- La tabla `events` es append-only y sirve de log de auditoría y base de futuras proyecciones.

## Consecuencias
- (+) Alineado al target (cero migración a futuro); pgvector ya disponible.
- (+) "Publicar evento = insertar fila", con atomicidad real (a diferencia de Sheets).
- (+) Evolución limpia: cambiar el dispatcher por un bus/relay de integration events sin tocar
  contratos de módulo.
- (+) Neon reanuda solo (~500 ms) tras scale-to-zero; sin pausa manual.
- (−) El dispatch síncrono in-process no es tolerante a fallos como un bus; se mitiga con
  reproceso desde `events` e idempotencia por `event_type + aggregate_id`.

## Alternativas
- **Google Sheets** → rechazada (no es DB real; migración inmediata).
- **Bus/broker real (Kafka/Rabbit) ya en el MVP** → over-engineering para el slice humano.
