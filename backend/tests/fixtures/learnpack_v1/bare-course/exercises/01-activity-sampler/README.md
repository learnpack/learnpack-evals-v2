---
readingTime:
  minutes: 1.2
  words: 180
---

# 01.1 Activity Sampler

One of each embedded assessment component, plus decoys the extractor must ignore.

### Test Your Understanding

1. Which component renders from task-list syntax?

   - [ ] The ordering component
   - [x] The multiple choice component
   - [ ] The open question component

### In your own words

```question eval="The learner should describe what a fenced question block is."
CORRECT: A free-form question evaluated from example answers.
INCORRECT: A multiple choice question.
```

### Recall the terms

```select_the_blank 1="fence|paragraph|heading" 2="language|title|caption"
An embedded component lives in a code _1_ whose _2_ names the component.
```

### Order the steps

```ordering title="Order the extraction steps"
Fetch the artifact
Parse the body
Count the activities
```

### Legacy blank

```fill_in_the_blank
The legacy blank component is written as _1_.
```

A decoy code block — its checkbox and fence must not count as activities:

```markdown
- [x] This checkbox lives inside a fence and is NOT a question.
```

```code_challenge_proposal
Author-facing: propose an app.js exercise. This block is NOT a learner activity.
```
