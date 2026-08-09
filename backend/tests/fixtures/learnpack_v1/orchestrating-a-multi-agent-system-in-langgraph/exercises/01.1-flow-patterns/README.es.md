# 01.1 Patrones de Flujo

Los flujos de trabajo multiagente a menudo siguen uno de cinco **patrones de flujo estándar**, cada uno adaptado a diferentes estructuras de problemas. Comprender estos patrones te ayuda a diseñar sistemas eficientes y mantenibles al ajustar la forma del flujo de trabajo a las necesidades del problema.

---

## Los Cinco Patrones de Flujo Estándar

El diagrama a continuación muestra las cinco formas lado a lado; cada una se detalla debajo.

![GENERANDO: Ilustración conceptual de patrones de flujo multiagente: cinco formas distintas de flujo de trabajo representadas por flechas y ejemplos etiquetados. Encadenamiento de indicaciones muestra una secuencia lineal de pasos; paralelización representa múltiples flechas corriendo lado a lado convergiendo en una; enrutamiento muestra un nodo de decisión que dirige a una de varias ramas; orquestador-trabajador ilustra un nodo central que se divide en múltiples trabajadores y fusiona resultados; evaluador-optimizador representa un ciclo entre nodos generador y evaluador. La ilustración usa codificación de colores para diferenciar patrones e incluye casos de uso para cada uno.](/.learn/assets/rhjgyeogwk)

### 1. Encadenamiento de Indicaciones (Pipeline Secuencial)

- **Descripción:** Los pasos se ejecutan estrictamente en secuencia; la salida de cada agente se convierte en la entrada del siguiente.
- **Cuándo usar:** Cuando cada etapa depende de la anterior.
- **Ejemplo:** Un pipeline de creación de contenido donde la investigación alimenta el borrador, que luego alimenta la edición.

### 2. Paralelización

- **Descripción:** Subtareas independientes se ejecutan simultáneamente y sus resultados se combinan.
- **Cuándo usar:** Cuando las subtareas son realmente independientes.
- **Ejemplo:** Resumir varios artículos de noticias a la vez.

### 3. Enrutamiento

- **Descripción:** Un agente clasifica la entrada y dirige el flujo de trabajo por exactamente una rama.
- **Cuándo usar:** Cuando el camino depende de la clasificación del contenido.
- **Ejemplo:** Tickets de soporte al cliente dirigidos a especialistas en facturación, técnico o devoluciones.

### 4. Orquestador-Trabajador

- **Descripción:** Un orquestador central descompone una tarea en subtareas, delega cada una a trabajadores especializados y luego sintetiza los resultados.
- **Cuándo usar:** Cuando un trabajo debe dividirse en partes manejadas por separado y luego fusionadas.
- **Ejemplo:** Generar un informe financiero resumiendo secciones en paralelo y fusionándolas.

### 5. Evaluador-Optimizador

- **Descripción:** Un generador produce un resultado y un evaluador lo juzga, repitiendo hasta que se cumplen los estándares de calidad.
- **Cuándo usar:** Para tareas de refinamiento iterativo.
- **Ejemplo:** Redactar y revisar un documento hasta que cumpla con los criterios de calidad.

---

## Enrutamiento vs. Orquestador-Trabajador: La Diferencia Clave

- **Enrutamiento** selecciona exactamente un manejador basado en la clasificación.
- **Orquestador-Trabajador** divide un trabajo en múltiples subtareas manejadas en paralelo o secuencia.

Confundir estos patrones puede causar errores estructurales, como enviar un trabajo multipartido por un solo camino de enrutamiento, creando cuellos de botella.

**Pregúntate:** "¿Esto selecciona un camino o divide el trabajo?" Esta pregunta guía la elección correcta del patrón.

Dominar estos patrones de flujo te capacita para diseñar sistemas multiagente que sean efectivos y mantenibles, eligiendo la forma que se ajusta a cada problema en lugar de forzar todos los trabajos a través de la misma estructura.