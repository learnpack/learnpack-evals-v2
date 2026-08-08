---
readingTime:
  minutes: 1.17
  words: 293
fkglResult: 8.5
---

# 02.1 Links and Navigation

Links are what turn separate pages into a connected website. The **anchor tag** `<a>` creates a link, and its `href` attribute says where the link goes. Grouping those links into a navigation menu is how visitors move around your site.

## Creating Links

To link to an external site, use an **absolute URL** with the full web address:

```html
<a href="https://twitter.com">Visit Twitter</a>
```

For pages within your own project, use a **relative URL** that points to a file in your folder. This keeps the site portable:

```html
<a href="about.html">About Us</a>
```

You can also jump to a section on the *same* page. Give the target element an `id`, then link to it with a `#`:

```html
<h2 id="features">Features</h2>
<a href="#features">Jump to Features</a>
```

To open a link in a new browser tab — useful for external links so visitors keep your site open — add `target="_blank"`:

```html
<a href="https://instagram.com" target="_blank">Instagram Profile</a>
```

Whatever the destination, write **descriptive link text** that names where the link goes. "About our team" is clear; "click here" tells a screen-reader user nothing and helps no one.

## Building a Semantic Navigation Menu

A navigation menu is really just a *list of links*, so the semantic way to build it is an unordered list inside a `<nav>` element:

```html
<nav>
  <ul>
    <li><a href="index.html" aria-current="page">Home</a></li>
    <li><a href="about.html">About</a></li>
    <li><a href="contact.html">Contact</a></li>
  </ul>
</nav>
```

Each part pulls its weight: `<nav>` tells browsers and assistive technology "this is a block of navigation," `<ul>` and `<li>` express that the links belong together as a group, and `aria-current="page"` marks the link for the page you are currently on so a screen reader can announce it.

To build a multi-page site, place this same menu on every page and move `aria-current="page"` to whichever link matches the current page. That consistency is what lets visitors always know where they are and how to get somewhere else — the quiet backbone of a site that feels easy to use.
