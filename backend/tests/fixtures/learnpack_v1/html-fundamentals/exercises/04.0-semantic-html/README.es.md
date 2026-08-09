---
readingTime:
  minutes: 1.95
  words: 488
fkglResult: 9.0
---

# 04.0 HTML semántico

HTML semántico significa elegir las etiquetas por lo que *significan*, no por cómo se ven. En lugar de apilar cajas genéricas, describes tu contenido — y esa descripción es lo que hace que una página sea accesible, fácil de encontrar y de mantener.

![/.learn/assets/semantic-html.png](/.learn/assets/semantic-html.png)

## Semántico vs. no semántico

Un **elemento semántico** describe su contenido: `<header>`, `<nav>`, `<main>`, `<footer>`, `<article>`, `<section>`, `<aside>`. Un **elemento no semántico** como `<div>` o `<span>` es solo un contenedor genérico sin significado propio.

Envolver una entrada de blog en `<article>` en lugar de `<div>` da frutos de tres maneras:

- **Accesibilidad** — los lectores de pantalla usan estos puntos de referencia para que los usuarios salten directamente a la navegación o al contenido principal.
- **SEO** — los motores de búsqueda leen la estructura para entender qué es importante en la página.
- **Mantenibilidad** — `<nav>` le dice al siguiente desarrollador "esto es el menú" mucho mejor que `<div class="nav">`.

## Elementos estructurales

Cuatro elementos le dan a una página su esqueleto general:

- `<header>` — contenido introductorio o identidad del sitio (logo, título), como la barra superior de Instagram.
- `<nav>` — los enlaces de navegación principales.
- `<main>` — el contenido principal y único de esta página (usa solo uno por página).
- `<footer>` — información de cierre como derechos de autor o datos de contacto.

![GENERATING: Conceptual illustration of a web page layout showing semantic elements: a large rectangle labeled "Page" containing nested boxes labeled "Header" with site title and intro text, "Nav" with a list of links, "Main" with an article containing a heading and paragraph, and "Footer" with copyright info. Arrows and labels highlight the roles and relationships of these elements, emphasizing their semantic meaning and how they organize content for accessibility and clarity. The illustration uses friendly colors and clear annotations to help learners visualize the page structure.](/.learn/assets/hf07i9ltco)

```html
<header>
  <h1>My Website</h1>
</header>
<nav>
  <ul>
    <li><a href="index.html">Home</a></li>
    <li><a href="about.html">About</a></li>
  </ul>
</nav>
<main>
  <article>
    <h2>Latest News</h2>
    <p>Here is the latest update from our team.</p>
  </article>
</main>
<footer>
  <p>&copy; 2024 My Website. All rights reserved.</p>
</footer>
```

`<header>` y `<footer>` también pueden aparecer *dentro* de un artículo (para su propio título y autoría), y `<nav>` puede ubicarse dentro de un `<header>` cuando el menú forma parte de la barra superior.

## Elementos a nivel de contenido

Dentro de `<main>`, tres elementos más organizan el contenido en sí:

- `<article>` — contenido **autónomo y que se puede compartir de forma independiente**: una entrada de blog, una noticia, una ficha de producto. Debe tener sentido por sí solo.
- `<section>` — una **agrupación temática** dentro de una página o artículo, normalmente con su propio encabezado, como un capítulo.
- `<aside>` — contenido **tangencial** relacionado con el flujo principal pero que no forma parte de él: una barra lateral, un recuadro destacado, enlaces relacionados.

Estos se anidan de forma natural — un `<article>` puede contener varios elementos `<section>` más un `<aside>`:

```html
<article>
  <h1>Tech News Today</h1>
  <section>
    <h2>Latest Gadgets</h2>
    <p>New smartphones released this month...</p>
  </section>
  <aside>
    <h3>Editor's Picks</h3>
    <p>Check out these recommended reads.</p>
  </aside>
</article>
```

La habilidad está en hacer coincidir el elemento con el papel que juega su contenido — cuando cada parte de tu página está etiquetada por su significado, los navegadores, los motores de búsqueda y las personas que leen tu código la entienden todos de la misma manera.
