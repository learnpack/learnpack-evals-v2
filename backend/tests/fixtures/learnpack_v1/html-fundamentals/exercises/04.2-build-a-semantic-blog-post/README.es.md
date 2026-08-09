---
readingTime:
  minutes: 0.64
  words: 160
fkglResult: 6.5
---

# 04.2 Construye una entrada de blog semántica

Usa los elementos semánticos a nivel de contenido para estructurar una entrada de blog completa desde cero, eligiendo un tema que te guste (una receta favorita, cómo aprendiste a programar, consejos de viaje).

**Tu tarea:** completa `app.html` para que la entrada de blog esté organizada con `<article>`, `<section>` y `<aside>`.

- Envuelve toda la entrada en un único `<article>` con un `<h1>` para su título.
- Añade **dos** elementos `<section>` dentro del artículo, cada uno con su propio encabezado `<h2>` y al menos un párrafo.
- Añade un `<aside>` para contenido relacionado, con un encabezado de nivel inferior (como `<h3>`) y un párrafo corto o una lista.
- Anida todo correctamente (article → sections + aside) y mantén la jerarquía de encabezados en orden.

**Resultado esperado:** la página muestra una entrada de blog autónoma cuya estructura inspeccionada revela dos secciones temáticas y un aside anidados dentro de un único artículo, con los encabezados fluyendo h1 → h2 → h3.
