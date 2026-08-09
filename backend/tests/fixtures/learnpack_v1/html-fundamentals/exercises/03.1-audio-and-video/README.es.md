---
readingTime:
  minutes: 1.1
  words: 276
fkglResult: 8.5
---

# 03.1 Audio y video

HTML puede incrustar sonido y video directamente en una página — sin plugins ni reproductores externos. Las etiquetas `<audio>` y `<video>` funcionan casi de forma idéntica, así que una vez que conoces una, prácticamente conoces la otra.

## Incrustar audio

La etiqueta `<audio>` reproduce archivos de sonido como música, podcasts o efectos. Añade el atributo **controls** para darles a los usuarios una interfaz de reproducción/pausa/volumen:

```html
<audio src="podcast.mp3" controls></audio>
```

También puedes hacer que el audio empiece solo con **autoplay** y se repita con **loop**. En la práctica, los navegadores bloquean la reproducción automática a menos que el audio esté también **muted** (silenciado) o el usuario ya haya interactuado con la página:

```html
<audio src="background-music.mp3" autoplay loop muted></audio>
```

Usa la reproducción automática con moderación — un sonido inesperado es una de las formas más rápidas de molestar a un visitante.

## Incrustar video

La etiqueta `<video>` funciona de la misma manera, con **controls** para la reproducción y **width**/**height** para dimensionar el reproductor:

```html
<video src="demo.mp4" controls width="640" height="360">
  Your browser does not support the video tag.
</video>
```

Los navegadores admiten distintos formatos de video, así que para una reproducción fiable puedes ofrecer varios archivos usando elementos `<source>` — el navegador elige el primero que entiende:

```html
<video controls width="640" height="360">
  <source src="demo.mp4" type="video/mp4">
  <source src="demo.webm" type="video/webm">
  Video not supported.
</video>
```

El atributo `loop` hace que un video se repita, igual que con el audio.

## Contenido alternativo

El texto que colocas entre las etiquetas de apertura y cierre del medio es el **contenido alternativo** — se muestra solo cuando el navegador no puede reproducir el elemento. Es una simple cortesía que les dice a los visitantes qué se están perdiendo y los dirige a una alternativa:

```html
<audio src="song.mp3" controls>
  Your browser does not support the audio element.
</audio>
```

Recurre al contenido alternativo en cada elemento de audio y video que añadas — cuesta una línea y hace que tu contenido multimedia se comporte con elegancia cuando algo sale mal.
