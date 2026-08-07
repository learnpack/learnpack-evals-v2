# ADR-0003 — Postgres (Neon) as store and events-first over an events table

**Status:** accepted · **Date:** 2026-07 · **Context:** the whole backend

## Context
The MVP needs persistence. Google Sheets was discarded (not a real DB, poor
querying/concurrency, no pgvector, awkward behind repository-ports). The target stack already uses
Postgres/pgvector, and we want to sustain the events-first approach without standing up a real bus yet.

## Decision
- **Neon (serverless Postgres, pgvector included)** as the store, behind repository-ports. The DB
  is an adapter; the logic lives in the domain.
- **Events-first realized as an outbox in Postgres:** each use case writes the aggregate and does an
  `INSERT` into an `events` table **in the same transaction**; after the commit, an **in-process
  dispatcher** delivers the event to the subscribed policies (synchronous in the MVP).
- The `events` table is append-only and serves as an audit log and the basis for future projections.

## Consequences
- (+) Aligned with the target (zero future migration); pgvector already available.
- (+) "Publishing an event = inserting a row", with real atomicity (unlike Sheets).
- (+) Clean evolution: swap the dispatcher for a bus/relay of integration events without touching
  module contracts.
- (+) Neon resumes on its own (~500 ms) after scale-to-zero; no manual pause.
- (−) The synchronous in-process dispatch is not fault-tolerant like a bus; mitigated with
  reprocessing from `events` and idempotency by `event_type + aggregate_id`.

## Alternatives
- **Google Sheets** → rejected (not a real DB; immediate migration).
- **Real bus/broker (Kafka/Rabbit) already in the MVP** → over-engineering for the human slice.
