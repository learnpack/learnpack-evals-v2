---
readingTime:
  minutes: 1.79
  words: 447
fkglResult: 10.74
---

# 01.1 Flow Patterns

Multi-agent workflows often follow one of five **standard flow patterns**, each tailored to different problem structures. Understanding these patterns helps you design efficient, maintainable systems by matching the workflow shape to the problem's needs.

---

## The Five Standard Flow Patterns

The diagram below shows the five shapes side by side; each one is detailed underneath.

![GENERATING: Conceptual illustration of multi-agent flow patterns: five distinct workflow shapes represented by arrows and labeled examples. Prompt chaining shows a linear sequence of steps; parallelization depicts multiple arrows running side-by-side converging into one; routing shows a decision node directing to one of several branches; orchestrator-worker illustrates a central node splitting into multiple workers and merging results; evaluator-optimizer depicts a loop between generator and evaluator nodes. The illustration uses color coding to differentiate patterns and includes example use cases for each.](/.learn/assets/rhjgyeogwk)

### 1. Prompt Chaining (Sequential Pipeline)

- **Description:** Steps run strictly in sequence; each agent's output becomes the next agent's input.
- **When to use:** When each stage depends on the previous one.
- **Example:** A content creation pipeline where research feeds drafting, which then feeds editing.

### 2. Parallelization

- **Description:** Independent subtasks run simultaneously, and their results are combined.
- **When to use:** When subtasks are truly independent.
- **Example:** Summarizing multiple news articles at once.

### 3. Routing

- **Description:** One agent classifies the input and directs the workflow down exactly one branch.
- **When to use:** When the path depends on the content classification.
- **Example:** Customer support tickets routed to billing, technical, or returns specialists.

### 4. Orchestrator-Worker

- **Description:** A central orchestrator decomposes a task into subtasks, delegates each to specialized workers, then synthesizes the results.
- **When to use:** When a job must be split into parts handled separately and then merged.
- **Example:** Generating a financial report by summarizing sections in parallel and merging them.

### 5. Evaluator-Optimizer

- **Description:** A generator produces a result, and an evaluator judges it, looping until quality standards are met.
- **When to use:** For iterative refinement tasks.
- **Example:** Drafting and revising a document until it meets quality criteria.

---

## Routing vs. Orchestrator-Worker: The Key Difference

- **Routing** selects exactly one handler based on classification.
- **Orchestrator-Worker** splits one job into multiple subtasks handled in parallel or sequence.

Confusing these patterns can cause structural errors, such as sending a multi-part job down a single routing path, creating bottlenecks.

**Ask yourself:** "Does this select one path or split the job?" This question guides the correct pattern choice.

Mastering these flow patterns equips you to design multi-agent systems that are both effective and maintainable, choosing the shape that fits each problem rather than forcing every job through the same structure.