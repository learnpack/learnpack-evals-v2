---
readingTime:
  minutes: 0.96
  words: 241
fkglResult: 8.5
---

# 03.1 Audio and Video

HTML can embed sound and video directly in a page — no plugins or external players needed. The `<audio>` and `<video>` tags work almost identically, so once you know one, you mostly know the other.

## Embedding Audio

The `<audio>` tag plays sound files like music, podcasts, or effects. Add the **controls** attribute to give users a play/pause/volume interface:

```html
<audio src="podcast.mp3" controls></audio>
```

You can also make audio start on its own with **autoplay** and repeat with **loop**. In practice, browsers block autoplay unless the audio is also **muted** or the user has already interacted with the page:

```html
<audio src="background-music.mp3" autoplay loop muted></audio>
```

Use autoplay sparingly — unexpected sound is one of the fastest ways to annoy a visitor.

## Embedding Video

The `<video>` tag works the same way, with **controls** for playback and **width**/**height** to size the player:

```html
<video src="demo.mp4" controls width="640" height="360">
  Your browser does not support the video tag.
</video>
```

Browsers support different video formats, so for reliable playback you can offer several files using `<source>` elements — the browser picks the first one it understands:

```html
<video controls width="640" height="360">
  <source src="demo.mp4" type="video/mp4">
  <source src="demo.webm" type="video/webm">
  Video not supported.
</video>
```

The `loop` attribute makes a video repeat, just as it does for audio.

## Fallback Content

The text you place between the opening and closing media tags is **fallback content** — it displays only when the browser cannot play the element. It is a simple courtesy that tells visitors what they are missing and points them to an alternative:

```html
<audio src="song.mp3" controls>
  Your browser does not support the audio element.
</audio>
```

Reach for fallback content on every audio and video element you add — it costs one line and makes your media graceful when something goes wrong.
