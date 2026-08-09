# 02.0 De Bucles de Herramientas a ToolNode

En tu viaje con LangGraph, has dominado la construcción de agentes que despachan herramientas manualmente en un bucle. Ahora, es momento de evolucionar ese enfoque adoptando el **ToolNode** — un bloque de construcción poderoso que simplifica la ejecución de herramientas y ancla tus agentes en un **estado de grafo** compartido.

## ¿Por qué reemplazar el despacho manual de herramientas?

El despacho manual de herramientas implica escribir código para:

- Inspeccionar las respuestas del modelo en busca de llamadas a herramientas
- Buscar e invocar la herramienta correcta
- Manejar errores de forma elegante
- Añadir los resultados de las herramientas de nuevo a la conversación

Aunque esto funciona, rápidamente se vuelve frágil y repetitivo. Cada proyecto requiere el mismo código base, aumentando la posibilidad de errores y la carga de mantenimiento.

## Presentamos el ToolNode

El **ToolNode** encapsula toda la lógica de despacho manual en un solo nodo reutilizable. Cuando le proporcionas una lista de herramientas, él:

- Lee el último mensaje del modelo desde el estado de grafo compartido
- Ejecuta todas las llamadas a herramientas solicitadas
- Captura cualquier error
- Escribe los resultados de las herramientas de vuelta en el estado de grafo como mensajes estructurados

Esto significa que ya no tienes que manejar los detalles frágiles tú mismo — el ToolNode lo hace de manera consistente y confiable.

## El Estado de Grafo Compartido: El Patrón Pizarra

En LangGraph, los nodos no se comunican llamándose directamente. En cambio, coordinan a través de un **estado de grafo** tipado y compartido — una pizarra dinámica donde todos los agentes y herramientas leen y escriben.

![GENERANDO: Ilustración conceptual que muestra un estado de grafo compartido central representado como una pizarra, con flechas que indican un nodo modelo escribiendo mensajes al estado, el ToolNode leyendo llamadas a herramientas del estado, ejecutando herramientas y escribiendo resultados de herramientas de vuelta. La ilustración usa cajas codificadas por colores para el nodo modelo, ToolNode y herramientas, conectados mediante flechas al estado compartido, enfatizando el patrón pizarra de coordinación.](/.learn/assets/me98q5kds7)

- El nodo modelo añade sus respuestas a este estado.
- El ToolNode lee estas respuestas para encontrar llamadas a herramientas.
- Después de ejecutar las herramientas, el ToolNode escribe los resultados de vuelta en el estado.

Este estado compartido asegura una comunicación clara y estructurada y evita conjeturas o entregas ambiguas en lenguaje natural.

## Por qué esto importa

Usar un ToolNode y un estado de grafo compartido:

- **Simplifica tu código** eliminando el código base de despacho manual
- **Mejora la confiabilidad** con manejo de errores y actualizaciones de estado consistentes
- **Permite flujos de trabajo multiagente más ricos** donde agentes y herramientas coordinan a través de una pizarra común
- **Escala mejor** a medida que tu sistema crece en complejidad

Juntos, el ToolNode y el estado de grafo compartido forman la base para orquestar flujos de trabajo multiagente complejos, reemplazando el despacho frágil escrito a mano con un bloque de construcción confiable y preconstruido.