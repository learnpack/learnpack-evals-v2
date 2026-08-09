# 01.0 Qué es un flujo de trabajo de agentes

Entender cómo colaboran los agentes en un sistema es clave para diseñar flujos de trabajo multiagente efectivos. Esta lección explora qué es un flujo de trabajo de agentes, dónde se sitúan los sistemas en el espectro de control de flujo y cómo decidir cuándo dividir responsabilidades entre agentes especializados.

---

## ¿Qué es un flujo de trabajo de agentes?

Un **flujo de trabajo de agentes** es un sistema estructurado donde modelos de lenguaje y herramientas están conectados mediante un proceso definido para cumplir una tarea. La pregunta central es: **¿Quién controla el flujo de acciones?**

### El espectro de control de flujo

Los sistemas se sitúan en algún punto entre dos extremos de este espectro:

- **Modelo de lenguaje integrado en rutas de código predefinidas:** Aquí, el desarrollador codifica la secuencia exacta de pasos. El modelo de lenguaje completa el contenido en cada paso, pero no decide el orden.

- **Modelo de lenguaje dirige el flujo de control:** El modelo elige qué camino tomar en cada punto de decisión, seleccionando herramientas o agentes dinámicamente dentro de opciones predefinidas.

La mayoría de los sistemas reales combinan estos enfoques, mezclando estructura predecible con decisiones guiadas por el modelo en puntos clave.

---

## Cuándo usar un agente o varios agentes

Decidir si mantener un solo agente bien equipado o dividir el trabajo entre agentes especializados depende de la naturaleza del problema:

- Usa **un agente** cuando la tarea es coherente y el conjunto de herramientas es pequeño y relacionado.
- Usa **varios agentes** cuando la tarea abarca diferentes áreas de especialización, cuando las instrucciones se contradicen si se combinan, o cuando las partes pueden ejecutarse de forma independiente.

Dividir agentes introduce sobrecarga de coordinación pero mejora la claridad, mantenibilidad y potencial paralelismo.

---

## Reglas de diseño para dividir agentes

Para construir sistemas multiagente mantenibles, sigue estas mejores prácticas:

1. **Un propósito por agente:** Cada agente tiene un rol claro y especializado (por ejemplo, planificador, ejecutor, verificador).
2. **Interfaces explícitas y tipadas:** Los agentes se comunican mediante mensajes bien definidos y estructurados, no lenguaje natural vago.
3. **Reemplazabilidad:** Los agentes pueden ser intercambiados o actualizados independientemente sin romper el sistema.
4. **Orquestador sin estado:** El orquestador delega tareas pero no ejecuta lógica de dominio.

Estas reglas existen porque sus opuestos son modos comunes de fallo. Un agente "todólogo" que intenta hacerlo todo colapsa bajo la complejidad y errores; agentes ciegos que actúan sin contexto suficiente producen resultados desalineados; un orquestador que realiza lógica de dominio se convierte en cuello de botella y erosiona la modularidad; y el lenguaje natural libre entre agentes genera ambigüedad y propaga errores.

---

## Escenario de ejemplo

Imagina un sistema de soporte al cliente:

- Un **agente de triaje** clasifica los tickets entrantes.
- Agentes especializados manejan **facturación**, **soporte técnico** o **devoluciones**.
- El orquestador enruta las solicitudes pero no resuelve los problemas por sí mismo.

Esta división clara mejora la precisión y escalabilidad.

Dominando estos conceptos, estarás preparado para diseñar flujos de trabajo multiagente que equilibren control, claridad y colaboración, dividiendo el trabajo solo cuando el problema realmente lo demande.