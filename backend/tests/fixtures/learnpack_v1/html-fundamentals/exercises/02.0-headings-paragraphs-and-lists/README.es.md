---
readingTime:
  minutes: 1.59
  words: 398
fkglResult: 8.5
---

# 02.0 Encabezados, párrafos y listas

Los encabezados, los párrafos y las listas son la forma de convertir una página en blanco en contenido organizado y legible. Hacen más que mostrar texto — definen la jerarquía y la agrupación en las que tanto los lectores como los navegadores se apoyan para darle sentido a una página.

## Los encabezados crean un esquema

HTML ofrece seis niveles de encabezado, de `<h1>` a `<h6>`, cada uno señalando un nivel de importancia. Usados correctamente, forman un **esquema del documento** que ayuda a las personas a escanear la página, permite a los lectores de pantalla saltar entre secciones e indica a los motores de búsqueda cómo está organizado tu contenido.

![/.learn/assets/jsfiddle-code-playground-02-06-2026_04_39_pm.png](/.learn/assets/jsfiddle-code-playground-02-06-2026_04_39_pm.png)

Unas pocas reglas mantienen ese esquema con sentido:

- Usa exactamente un `<h1>` por página como título principal.
- Ve en orden — `<h1>`, luego `<h2>`, luego `<h3>` — y nunca saltes un nivel (no pases de `<h1>` a `<h4>`).
- Elige un encabezado por su lugar en la estructura, no porque quieras un texto más grande.

```html
<h1>My Travel Blog</h1>
<h2>Europe Trip</h2>
<p>Europe offers a rich tapestry of cultures, history, and cuisine.</p>
<h3>Paris Highlights</h3>
<p>Visiting the Eiffel Tower was unforgettable.</p>
```

## Los párrafos agrupan texto relacionado

La etiqueta `<p>` agrupa oraciones relacionadas en un párrafo, dividiendo el contenido en bloques legibles. Para un verdadero salto de línea *dentro* de un párrafo — una dirección o unos versos de un poema — usa el elemento vacío `<br>`:

```html
<p>
123 Main Street<br>
Springfield, USA
</p>
```

Usa `<br>` con moderación y solo cuando el salto tenga significado. Nunca apiles varias etiquetas `<br>` para crear espacio entre párrafos — para eso están los elementos `<p>` separados.

## Las listas agrupan elementos relacionados

Cuando el contenido es una colección de elementos, una lista expresa esa relación. HTML te da tres tipos:

**Listas desordenadas (`<ul>`)** — cuando el orden no importa, como un menú de navegación o un conjunto de características:

```html
<ul>
  <li>Home</li>
  <li>Explore</li>
  <li>Messages</li>
</ul>
```

**Listas ordenadas (`<ol>`)** — cuando la secuencia importa, como los pasos de una receta o resultados clasificados:

```html
<ol>
  <li>Preheat oven to 350°F</li>
  <li>Mix ingredients</li>
  <li>Bake for 30 minutes</li>
</ol>
```

**Listas de descripción (`<dl>`)** — para pares de término y definición, como un glosario o unas preguntas frecuentes, usando `<dt>` para el término y `<dd>` para su descripción:

```html
<dl>
  <dt>HTML</dt>
  <dd>HyperText Markup Language, the standard markup language for web pages.</dd>
</dl>
```

Las listas también pueden anidarse unas dentro de otras para mostrar jerarquía, como categorías con subcategorías:

```html
<ul>
  <li>Fruits
    <ul>
      <li>Apples</li>
      <li>Oranges</li>
    </ul>
  </li>
  <li>Vegetables</li>
</ul>
```

Elegir el tipo de lista que coincide con el *significado* de tu contenido — y no solo con su apariencia — es lo que hace que una página sea fácil de interpretar para los lectores de pantalla y fácil de mantener para ti más adelante.
