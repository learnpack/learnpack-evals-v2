---
readingTime:
  minutes: 1.65
  words: 413
fkglResult: 8.5
---

# 01.1 El esqueleto HTML, las etiquetas y los atributos

Cada página HTML parte del mismo esqueleto básico, construido con etiquetas, elementos y atributos. Una vez que reconoces estos bloques de construcción, puedes leer y escribir cualquier documento HTML con confianza.

## El esqueleto del documento

Esta es la estructura mínima que necesita cada página:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <title>Sample Page</title>
  </head>
  <body>
    <h1>Hello World</h1>
    <p>This is a simple HTML document.</p>
  </body>
</html>
```

Cada parte tiene una función:

- `<!DOCTYPE html>` le indica al navegador que renderice la página en modo estándar (esto es HTML5).
- `<html lang="en">` es el elemento raíz que envuelve todo el documento; `lang` declara el idioma para los motores de búsqueda y los lectores de pantalla.
- `<head>` contiene los metadatos que el usuario no ve directamente — `<meta charset="UTF-8">` define la codificación de caracteres para que el texto de cualquier idioma se muestre correctamente, y `<title>` nombra la pestaña del navegador (y es importante para el SEO).
- `<body>` contiene todo lo visible: encabezados, párrafos, imágenes y lo demás.

## Etiquetas y elementos

Una **etiqueta** es el marcado que escribes, como `<p>` o `<img>`. Un **elemento** es el paquete completo: la etiqueta de apertura, el contenido y la etiqueta de cierre juntos. En `<p>Hello</p>`, `<p>` y `</p>` son etiquetas, y todo el `<p>Hello</p>` es el elemento.

![/.learn/assets/shs4nx3l6g.png](/.learn/assets/shs4nx3l6g.png)

La mayoría de los elementos vienen en pares: una **etiqueta de apertura** (`<p>`) y una **etiqueta de cierre** (`</p>`) con el contenido en medio.

### Elementos vacíos

Algunos elementos no tienen contenido y, por lo tanto, no tienen etiqueta de cierre — son los **elementos vacíos** (void elements), y se cierran a sí mismos. Los más comunes son:

- `<img>` — inserta una imagen.
- `<br>` — inserta un salto de línea.
- `<input>` — crea un campo de formulario.

```html
<img src="profile.jpg" alt="User profile picture">
```

Observa que no hay `</img>`.

## Atributos

Los **atributos** añaden información adicional a un elemento, escritos como pares `nombre="valor"` dentro de la etiqueta de apertura:

```html
<img src="photo.jpg" alt="Sunset over mountains" width="300">
```

Aquí `src` apunta al archivo de imagen, `alt` lo describe para la accesibilidad y `width` define su ancho de visualización. Siempre encierra los valores de los atributos entre comillas dobles.

## Errores comunes que debes evitar

Los errores más frecuentes de los principiantes son olvidar una etiqueta de cierre (excepto en los elementos vacíos), dejar los valores de atributos sin comillas y escribir mal el nombre de una etiqueta o atributo:

```html
<img src=photo.jpg alt=Sunset>
```

Los navegadores intentarán reparar un marcado como este, pero los resultados son impredecibles — así que vale la pena cerrar tus etiquetas, poner comillas en tus valores y mantener un anidamiento ordenado desde el principio.
