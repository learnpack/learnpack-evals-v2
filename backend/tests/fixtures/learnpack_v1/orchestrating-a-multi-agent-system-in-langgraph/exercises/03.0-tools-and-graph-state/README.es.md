# 03.0 Herramientas y Estado del Grafo

En sistemas multiagente construidos con LangGraph, las herramientas no son ayudantes aislados; son participantes activos en un espacio de trabajo compartido llamado **estado del grafo**. Este estado compartido actúa como una pizarra donde agentes y herramientas leen y escriben información para coordinar su trabajo sin problemas.

## Lectura del Estado del Grafo con ToolRuntime

Las herramientas a menudo necesitan acceso a información más allá de sus entradas directas — por ejemplo, el ID del usuario actual, el nivel de cuenta u otro contexto almacenado en el estado del grafo. En lugar de pasar todos estos datos a través del prompt del modelo o los argumentos de la herramienta, las herramientas pueden acceder directamente a ellos mediante un parámetro inyectado llamado **ToolRuntime**.

Así es como declaras una herramienta que lee del estado del grafo:

```python
from langchain.tools import tool, ToolRuntime

@tool
def get_user_orders(runtime: ToolRuntime) -> str:
    """Lista los pedidos recientes del usuario actual."""
    user_id = runtime.state["user_id"]  # Accede directamente al estado del grafo
    return f"Pedidos recientes para el usuario {user_id}: #1021, #1044."
```

Observa que `runtime` es proporcionado automáticamente por LangGraph y está oculto para el modelo, por lo que el modelo nunca necesita suministrar ni siquiera conocer estos datos.

## Escritura de Actualizaciones al Estado del Grafo con Command

Las herramientas también pueden actualizar el estado del grafo devolviendo un objeto **Command**. Esto permite que las herramientas escriban datos estructurados y mensajes, manteniendo un flujo claro y consistente de información.

Ejemplo:

```python
from langgraph.types import Command
from langchain.messages import ToolMessage

@tool
def set_shipping_preference(value: str, runtime: ToolRuntime) -> Command:
    """Guarda la preferencia de envío del cliente en el estado del grafo."""
    return Command(update={
        "shipping_preference": value,
        "messages": [ToolMessage("Preferencia guardada.", tool_call_id=runtime.tool_call_id)],
    })
```

Este comando actualiza la clave `shipping_preference` en el estado del grafo y añade un mensaje de herramienta confirmando la acción.

Para mantener estas interacciones manejables, limita cada herramienta solo al estado que necesita en lugar de toda la historia de la conversación o datos no relacionados—esto reduce la sobrecarga de contexto, mejora el rendimiento y previene acoplamientos no deseados. Define límites de estado tipados con subclases de `TypedDict` para que sea explícito qué claves una herramienta lee o escribe, creando contratos claros entre agentes y herramientas. Y versiona tu esquema de estado para que, a medida que los agentes evolucionen independientemente, las incompatibilidades se detecten temprano en lugar de fallar silenciosamente.

Los modos de fallo son la imagen reflejada de estas prácticas. Herramientas ciegas que actúan sin el estado que necesitan producen resultados obsoletos o incorrectos; pasar toda la historia de la conversación a cada herramienta infla el contexto y degrada el razonamiento; el lenguaje natural libre entre agentes conduce a ambigüedad y propagación de errores; y el estado mutable compartido escrito por múltiples escritores no coordinados causa condiciones de carrera que corrompen el estado.

Entender estos principios—acceder al estado a través del **ToolRuntime** inyectado, escribir actualizaciones con **Command**, y limitar cada herramienta a la mínima porción de estado que necesita—es esencial para construir flujos de trabajo multiagente mantenibles y escalables.