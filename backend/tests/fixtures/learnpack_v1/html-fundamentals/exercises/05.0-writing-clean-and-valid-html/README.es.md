---
readingTime:
  minutes: 2.04
  words: 509
fkglResult: 8.5
---

# 05.0 Escribir HTML limpio y válido

HTML que funciona y HTML *bueno* no son lo mismo. Un marcado limpio y válido es más fácil de leer, más fácil de depurar y más fácil de mantener para la siguiente persona (a menudo, tú en el futuro). Tres hábitos te llevan ahí: escríbelo de forma limpia, valídalo y evita las trampas comunes.

## Escribir HTML limpio

La **indentación consistente** es la mayor ganancia de legibilidad. Indenta los elementos hijos para que el anidamiento se vea de un vistazo, usando 2 o 4 espacios de forma uniforme:

```html
<nav>
  <ul>
    <li><a href="index.html">Home</a></li>
    <li><a href="about.html">About</a></li>
  </ul>
</nav>
```

Más allá de la indentación, mantén tu estilo consistente:

- Usa nombres de etiqueta y atributo en minúsculas, y siempre pon comillas en los valores de los atributos.
- Ordena los atributos de forma predecible — `id`, luego `class`, luego el resto (`src`, `href`, `alt`).
- Añade **comentarios con significado** para marcar o explicar secciones no obvias (`<!-- Main navigation -->`), pero evita los comentarios que solo repiten lo evidente.
- Agrupa los elementos relacionados y separa los bloques principales con una línea en blanco.

## Validar tu HTML

Incluso un marcado de aspecto ordenado puede ocultar errores estructurales. El [Validador HTML del W3C](https://validator.w3.org/), gratuito, revisa tu código: pégalo o sube el archivo, y enumerará cada error con su número de línea. Los más comunes son:

- **Etiquetas sin cerrar** — `<p>This is <strong>important text</p>` deja `<strong>` abierto. Ciérralo: `<strong>important text</strong>`.
- **IDs duplicados** — cada `id` debe ser único en una página; renombra uno del par en conflicto.
- **Anidamiento incorrecto** — las etiquetas de cierre deben reflejar el orden de apertura. `<p><em>text</p></em>` está mal; `<p><em>text</em></p>` está bien.

Las herramientas de desarrollo de tu navegador complementan al validador: abre **Inspeccionar** para ver el DOM que el navegador realmente construyó, y detectarás rápidamente una etiqueta que se cerró en el lugar equivocado.

## Anti-patrones comunes que debes evitar

Algunos hábitos funcionan visualmente pero rompen en silencio la accesibilidad y la mantenibilidad. Reconócelos para poder evitarlos:

- **Tablas para el diseño.** `<table>` es para datos tabulares, no para la estructura de la página. Usa elementos semánticos con CSS para el diseño.
- **Varias etiquetas `<br>` para espaciar.** Apilar `<br><br>` para empujar el contenido hacia abajo mezcla contenido con presentación; controla el espaciado con márgenes de CSS.
- **Estilos en línea.** `<div style="color:red">` es difícil de mantener; usa clases y una hoja de estilos externa.
- **`<div>` en lugar de un elemento semántico.** `<div class="heading">` debería ser un `<h2>`; un menú debería ser un `<nav>`. Recurre a la etiqueta con significado.
- **Saltarse niveles de encabezado.** Pasar de `<h2>` directamente a `<h4>` rompe el esquema; ve en orden.
- **Elementos vacíos para espaciar.** Un `<div></div>` vacío usado solo para crear un hueco es ruido — ese es trabajo de CSS.

Fíjate en el hilo que recorre todos estos casos: mantén la estructura (HTML) separada de la presentación (CSS), y deja que cada etiqueta signifique lo que dice. Escribe tu marcado con eso en mente, valídalo, y tus páginas se mantendrán limpias mucho después del primer borrador.
