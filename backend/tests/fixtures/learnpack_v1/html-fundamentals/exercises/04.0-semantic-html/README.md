---
readingTime:
  minutes: 1.74
  words: 436
fkglResult: 9.0
---

# 04.0 Semantic HTML

Semantic HTML means choosing tags for what they *mean*, not for how they look. Instead of stacking generic boxes, you describe your content — and that description is what makes a page accessible, discoverable, and maintainable.

![/.learn/assets/semantic-html.png](/.learn/assets/semantic-html.png)

## Semantic vs. Non-Semantic

A **semantic element** describes its content: `<header>`, `<nav>`, `<main>`, `<footer>`, `<article>`, `<section>`, `<aside>`. A **non-semantic element** like `<div>` or `<span>` is just a generic container with no meaning of its own.

Wrapping a blog post in `<article>` instead of `<div>` pays off in three ways:

- **Accessibility** — screen readers use these landmarks to let users jump straight to the navigation or main content.
- **SEO** — search engines read the structure to understand what matters on the page.
- **Maintainability** — `<nav>` tells the next developer "this is the menu" far better than `<div class="nav">`.

## Structural Elements

Four elements give a page its overall skeleton:

- `<header>` — introductory content or site branding (logo, title), like the top bar of Instagram.
- `<nav>` — the main navigation links.
- `<main>` — the primary content unique to this page (use only one per page).
- `<footer>` — closing information such as copyright or contact details.

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

`<header>` and `<footer>` can also appear *inside* an article (for its own title and byline), and `<nav>` can sit inside a `<header>` when the menu is part of the top bar.

## Content-Level Elements

Inside `<main>`, three more elements organize the content itself:

- `<article>` — **self-contained, independently shareable** content: a blog post, a news story, a product card. It should make sense on its own.
- `<section>` — a **thematic grouping** within a page or article, usually with its own heading, like a chapter.
- `<aside>` — **tangential** content related to the main flow but not part of it: a sidebar, a callout, related links.

These nest naturally — an `<article>` can hold several `<section>` elements plus an `<aside>`:

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

The skill is matching the element to the role its content plays — when every part of your page is labeled by meaning, browsers, search engines, and the people reading your code all understand it the same way.
