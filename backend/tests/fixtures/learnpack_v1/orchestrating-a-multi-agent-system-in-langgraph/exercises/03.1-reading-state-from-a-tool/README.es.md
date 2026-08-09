---
readingTime:
  minutes: 0.64
  words: 160
fkglResult: 9.0
---

# 03.1 Leer el Estado desde una Herramienta

Un agente de servicio al cliente necesita una estimación de envío que depende del nivel de cuenta del cliente, y ese nivel ya reside en el estado del grafo en lugar de en el prompt del modelo.

**Tu tarea:** en `app.py`, implementa una herramienta que lea el nivel desde el estado del grafo y devuelva una estimación de envío.

- Declara un `@tool` llamado `get_shipping_estimate` cuyo ÚNICO parámetro sea `runtime: ToolRuntime`.
- Lee la clave `account_tier` desde `runtime.state`.
- Devuelve una cadena de estimación de envío que refleje el nivel (los clientes premium obtienen una estimación más rápida que los estándar).
- El modelo NO debe suministrar el nivel — este proviene únicamente del estado de ejecución inyectado.

**Resultado esperado:** llamar a la herramienta con `account_tier` establecido en "premium" en el estado de ejecución devuelve una estimación de un día hábil, mientras que cualquier otro nivel devuelve una estimación más lenta.

Debido a que el nivel fluye a través del tiempo de ejecución, el modelo nunca tiene que conocerlo o pasarlo, manteniendo la herramienta autocontenida.