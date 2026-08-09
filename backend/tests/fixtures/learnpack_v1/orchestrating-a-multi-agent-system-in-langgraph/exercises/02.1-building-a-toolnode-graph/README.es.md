# 02.1 Construyendo un Grafo ToolNode

Has visto cómo un `ToolNode` reemplaza un bucle de despacho de herramientas escrito a mano; ahora conectarás uno en un grafo de agente funcional. En este desafío ensamblarás un `StateGraph` donde el modelo decide cuándo llamar a una herramienta, un `ToolNode` la ejecuta, y el resultado regresa al modelo.

**Tu tarea:** completa el grafo en `app.py` para que el bucle del agente funcione de principio a fin.

- Construye un `StateGraph` sobre `MessagesState` con un nodo "model" (la función `call_model` proporcionada) y un nodo "tools" que ejecute la herramienta `get_weather` a través de un `ToolNode`.
- Conecta el bucle: una arista desde `START` hacia "model", una arista condicional desde "model" usando la condición predefinida `tools_condition`, y una arista desde "tools" de regreso a "model".
- Compila el grafo e invócalo con una pregunta sobre el clima.

**Resultado esperado:** preguntar "¿Clima en París?" hace que el modelo llame a `get_weather`, el `ToolNode` la ejecute, y el modelo devuelva una respuesta final que incluya el clima.