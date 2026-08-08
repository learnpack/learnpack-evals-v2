---
readingTime:
  minutes: 1.4
  words: 349
fkglResult: 8.5
---

# 02.0 Headings, Paragraphs, and Lists

Headings, paragraphs, and lists are how you turn a blank page into organized, readable content. They do more than display text — they define the hierarchy and grouping that both readers and browsers rely on to make sense of a page.

## Headings Create an Outline

HTML offers six heading levels, `<h1>` through `<h6>`, each signaling a level of importance. Used correctly, they form a **document outline** that helps people scan the page, lets screen readers jump between sections, and tells search engines how your content is organized.

![/.learn/assets/jsfiddle-code-playground-02-06-2026_04_39_pm.png](/.learn/assets/jsfiddle-code-playground-02-06-2026_04_39_pm.png)

A few rules keep that outline meaningful:

- Use exactly one `<h1>` per page as the main title.
- Go in order — `<h1>`, then `<h2>`, then `<h3>` — and never skip a level (no jumping from `<h1>` to `<h4>`).
- Choose a heading for its place in the structure, not because you want bigger text.

```html
<h1>My Travel Blog</h1>
<h2>Europe Trip</h2>
<p>Europe offers a rich tapestry of cultures, history, and cuisine.</p>
<h3>Paris Highlights</h3>
<p>Visiting the Eiffel Tower was unforgettable.</p>
```

## Paragraphs Group Related Text

The `<p>` tag groups related sentences into a paragraph, breaking content into readable chunks. For a genuine line break *within* a paragraph — an address or a few lines of a poem — use the void element `<br>`:

```html
<p>
123 Main Street<br>
Springfield, USA
</p>
```

Use `<br>` sparingly and only when the break carries meaning. Never stack several `<br>` tags to create space between paragraphs — that is what separate `<p>` elements are for.

## Lists Group Related Items

When content is a collection of items, a list expresses that relationship. HTML gives you three kinds:

**Unordered lists (`<ul>`)** — when order does not matter, like a navigation menu or a set of features:

```html
<ul>
  <li>Home</li>
  <li>Explore</li>
  <li>Messages</li>
</ul>
```

**Ordered lists (`<ol>`)** — when sequence matters, like recipe steps or ranked results:

```html
<ol>
  <li>Preheat oven to 350°F</li>
  <li>Mix ingredients</li>
  <li>Bake for 30 minutes</li>
</ol>
```

**Description lists (`<dl>`)** — for term-and-definition pairs, like a glossary or FAQ, using `<dt>` for the term and `<dd>` for its description:

```html
<dl>
  <dt>HTML</dt>
  <dd>HyperText Markup Language, the standard markup language for web pages.</dd>
</dl>
```

Lists can also nest inside one another to show hierarchy, such as categories with subcategories:

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

Choosing the list type that matches the *meaning* of your content — not just its appearance — is what makes a page easy for screen readers to interpret and for you to maintain later.
