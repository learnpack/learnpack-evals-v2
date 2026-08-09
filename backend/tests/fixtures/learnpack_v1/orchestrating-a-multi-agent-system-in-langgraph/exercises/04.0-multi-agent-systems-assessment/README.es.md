# 04.0 Evaluación de Sistemas Multi-Agente

Selecciona la respuesta correcta para cada pregunta.

1. ¿Qué significa cuando un flujo de trabajo se describe como "el LLM dirige el flujo de control a través de rutas de código predefinidas"?

   - [ ] El desarrollador codifica manualmente la secuencia exacta de pasos y el modelo solo completa el contenido de cada paso.
   - [x] Los bloques de construcción están predefinidos, pero en cada punto de decisión el modelo elige qué camino tomar.
   - [ ] El modelo escribe nuevas rutas de código en tiempo de ejecución que no existían antes.
   - [ ] No hay estructura alguna: el modelo hace lo que quiere sin nodos predefinidos.

2. Notas que el prompt de un solo agente ha crecido para incluir reglas de facturación, solución técnica de problemas y políticas de devolución, causando confusión y errores. ¿Cuál es la mejor acción a tomar?

   - [ ] Cambiar a un modelo más grande y mantener un solo agente.
   - [x] Dividir responsabilidades en agentes especializados, cada uno con un propósito.
   - [ ] Eliminar herramientas para acortar el prompt.
   - [ ] Continuar con el diseño actual; se espera complejidad.

3. ¿Cuál es la diferencia clave entre los patrones de flujo routing y orchestrator-worker?

   - [ ] Routing descompone una tarea en subtareas paralelas; orchestrator-worker elige un manejador.
   - [ ] Son nombres intercambiables para el mismo patrón.
   - [x] Routing selecciona un camino para la solicitud; orchestrator-worker divide un trabajo en múltiples subtareas y fusiona los resultados.
   - [ ] Routing requiere un checkpointer; orchestrator-worker no.

4. ¿Por qué se prefiere un ToolNode sobre un ciclo manual de despacho de herramientas en LangGraph?

   - [ ] Hace que las llamadas al modelo sean más rápidas al omitir el modelo por completo.
   - [x] Empaqueta la búsqueda de herramientas, ejecución, captura de errores y escritura de resultados en el estado en un nodo preconstruido.
   - [ ] Elimina la necesidad de un modelo en el grafo.
   - [ ] Almacena automáticamente los resultados de las herramientas en una base de datos.

5. ¿Cómo debería una herramienta acceder al `account_tier` del usuario actual almacenado en el estado del grafo?

   - [ ] Añadir `account_tier` como un argumento normal de la herramienta para que el modelo lo pase.
   - [x] Declarar un parámetro `runtime: ToolRuntime` y leer `runtime.state["account_tier"]`.
   - [ ] Importar el objeto global del grafo y leer directamente su atributo `.state`.
   - [ ] Extraer el valor del historial de conversación dentro de la herramienta.

6. ¿Por qué una herramienta debería leer solo las claves específicas del estado de las que depende en lugar de todo el historial de conversación?

   - [ ] Leer todo el historial es imposible en LangGraph.
   - [x] Mantiene cada herramienta acotada y eficiente: menos sobrecarga de contexto, menor latencia y sin acoplamiento a estado no relacionado.
   - [ ] El historial completo está cifrado y no puede ser leído por las herramientas.
   - [ ] Las herramientas no tienen permitido leer el estado.

[Pregunta a Rigo sobre cómo diseñar sistemas multi-agente en LangGraph](https://4geeks.com/ask?query=how-to-design-multi-agent-systems-in-langgraph)