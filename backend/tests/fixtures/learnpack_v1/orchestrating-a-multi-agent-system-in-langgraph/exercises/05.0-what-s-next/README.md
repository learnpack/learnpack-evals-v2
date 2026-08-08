---
readingTime:
  minutes: 0.95
  words: 238
fkglResult: 11.0
---

# 05.0 What's Next

You've now built a solid mental model and the essential building blocks to design **multi-agent systems** that handle complexity with clarity and maintainability.

## What Comes Next?

With this foundation, you are ready to explore the rich landscape of multi-agent workflow patterns. The five standard flow patterns each build on what you've learned:

1. **Evaluator-Optimizer Loop:** Iteratively generate, evaluate, and improve outputs.
2. **Routing:** Classify inputs and direct requests down specific branches.
3. **Parallelization:** Run independent subtasks concurrently and combine results.
4. **Orchestrator-Worker:** Decompose complex tasks into subtasks handled by specialized workers, then synthesize.
5. **Prompt Chaining:** Sequentially process steps where each depends on the previous.

From there, advanced orchestration techniques like guardrails, iteration limits, tracing, and persistence features such as checkpointing and resuming become the next layer to master.

A good way to solidify these foundations is to extend the ToolNode graph you built: add a second tool that writes back to graph state with a `Command`, then introduce a routing decision so the model chooses between tools based on the request.

To go deeper, explore the official documentation:

- [LangGraph workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools)

With these building blocks in hand, you have everything you need to start designing multi-agent systems that stay clear and maintainable as they grow.
