---
readingTime:
  minutes: 2.35
  words: 588
fkglResult: 8.5
---

# 01.0 Qué es HTML y cómo lo leen los navegadores

Cada sitio web que has visitado — una red social, un artículo de noticias, una tienda en línea — está construido con **HTML** (Lenguaje de Marcado de Hipertexto). HTML es la columna vertebral de cada página web: proporciona la **estructura** y el **significado** del contenido, organizando texto, imágenes y enlaces en un documento coherente.

![/.learn/assets/vtxzvg6q5qd.jpg](/.learn/assets/vtxzvg6q5qd.jpg)

## Lo que HTML hace y lo que no hace

HTML define la estructura de una página usando **elementos** como encabezados, párrafos, listas y enlaces, y **etiquetas** que marcan el contenido para que el navegador sepa qué representa cada parte. Lo que deja deliberadamente de lado es igual de importante:

- HTML **no** controla cómo se ve una página — los colores, las fuentes y el diseño son trabajo de CSS.
- HTML **no** añade comportamiento ni interactividad — ese es el rol de JavaScript.
- HTML es un **lenguaje de marcado**, no un lenguaje de programación.

Esta división se llama **separación de responsabilidades**, y es la base de un desarrollo web limpio:

| Responsabilidad | Tecnología     | Propósito                                |
|-----------------|----------------|------------------------------------------|
| Estructura      | **HTML**       | Organiza y define el significado del contenido |
| Presentación    | **CSS**        | Estiliza y formatea visualmente el contenido |
| Comportamiento  | **JavaScript** | Añade interactividad y funciones dinámicas |

El mismo HTML puede verse completamente distinto con dos archivos CSS diferentes, y JavaScript puede hacer que un botón abra una ventana emergente — pero HTML es lo que define que el botón, el encabezado y la imagen existan en primer lugar.

## Cómo lee HTML el navegador: el árbol del DOM

Cuando un navegador carga tu HTML, no se limita a mostrar el texto tal cual. Analiza tu marcado y lo convierte en un modelo estructurado llamado **Modelo de Objetos del Documento (DOM)** — un árbol de elementos anidados, muy parecido a un árbol genealógico.

![GENERATING: Conceptual illustration of the DOM tree structure showing the <html> root node at the top, branching down to <body>, which further branches to <header> and <main>. <header> contains <h1>, and <main> branches to <section> and <aside>. Each node is connected with lines representing parent-child relationships, color-coded to differentiate levels, with annotations explaining siblings and nesting. The illustration uses a simplified, friendly style with flat colors to clarify the hierarchical nature of HTML documents.](/.learn/assets/x9z61k7oxj)

Observa este marcado:

```html
<html>
  <body>
    <header>
      <h1>My Blog</h1>
    </header>
    <main>
      <section>
        <p>Welcome to my blog!</p>
      </section>
      <aside>
        <p>Related links</p>
      </aside>
    </main>
  </body>
</html>
```

El navegador lo lee como una jerarquía:

- `<html>` es el **nodo raíz** que contiene todo.
- `<body>` es un **hijo** de `<html>`.
- `<header>` y `<main>` son **hermanos** — comparten el mismo padre.
- `<header>` contiene `<h1>` (su hijo), y `<main>` contiene el par de hermanos `<section>` y `<aside>`.

Estas relaciones de **padre–hijo** y de **hermanos** no son un dato trivial: son exactamente la forma en que CSS apunta a los elementos ("estiliza cada párrafo dentro de `<main>`") y cómo JavaScript los encuentra y los modifica después. En un sitio como Instagram, el feed es una serie de elementos `<article>` dentro de un `<main>`, mientras que la barra lateral de sugerencias es un `<aside>` — la misma estructura de árbol, sosteniendo contenido real.

## Observa el árbol tú mismo

Puedes inspeccionar el DOM de cualquier página en vivo: haz clic derecho en un elemento y elige **Inspeccionar** (o abre las herramientas de desarrollo de tu navegador). El panel de Elementos muestra la estructura anidada como un árbol plegable, así que puedes expandir nodos y observar las relaciones de padre–hijo y de hermanos que el navegador construyó a partir del HTML. Familiarizarte con la lectura de ese árbol es una de las formas más rápidas de entender cómo está armada cualquier página web.
