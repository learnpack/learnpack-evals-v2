# 05.0 Qué Sigue

Ahora has construido un modelo mental sólido y los bloques esenciales para diseñar **sistemas multiagente** que manejan la complejidad con claridad y mantenibilidad.

## ¿Qué Sigue?

Con esta base, estás listo para explorar el rico panorama de patrones de flujo de trabajo multiagente. Los cinco patrones estándar de flujo se basan en lo que has aprendido:

1. **Bucle Evaluador-Optimizador:** Generar, evaluar y mejorar salidas de forma iterativa.
2. **Enrutamiento:** Clasificar entradas y dirigir solicitudes por ramas específicas.
3. **Paralelización:** Ejecutar subtareas independientes concurrentemente y combinar resultados.
4. **Orquestador-Trabajador:** Descomponer tareas complejas en subtareas manejadas por trabajadores especializados, luego sintetizar.
5. **Encadenamiento de Prompts:** Procesar secuencialmente pasos donde cada uno depende del anterior.

A partir de ahí, técnicas avanzadas de orquestación como barreras de seguridad, límites de iteración, trazabilidad y características de persistencia como puntos de control y reanudación se convierten en la siguiente capa a dominar.

Una buena manera de solidificar estas bases es extender el grafo ToolNode que construiste: añade una segunda herramienta que escriba de nuevo en el estado del grafo con un `Command`, luego introduce una decisión de enrutamiento para que el modelo elija entre herramientas según la solicitud.

Para profundizar, explora la documentación oficial:

- [Flujos de trabajo y agentes de LangGraph](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [Herramientas de LangChain](https://docs.langchain.com/oss/python/langchain/tools)

Con estos bloques de construcción en mano, tienes todo lo necesario para comenzar a diseñar sistemas multiagente que se mantengan claros y mantenibles a medida que crecen.