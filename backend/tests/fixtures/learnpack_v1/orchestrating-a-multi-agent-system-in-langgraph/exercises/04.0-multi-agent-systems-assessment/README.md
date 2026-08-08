---
readingTime:
  minutes: 1.73
  words: 433
fkglResult: 9.0
---

# 04.0 Multi-Agent Systems Assessment

Select the correct answer for each question.

1. What does it mean when a workflow is described as "the LLM directs control flow through predefined code paths"?

   - [ ] The developer hard-codes the exact sequence of steps and the model only fills in each step's content.
   - [x] The building blocks are predefined, but at each decision point the model chooses which path to take.
   - [ ] The model writes new code paths at runtime that did not exist before.
   - [ ] There is no structure at all — the model does whatever it wants with no predefined nodes.

2. You notice a single agent's prompt has grown to include billing rules, technical troubleshooting, and return policies, causing confusion and errors. What is the best course of action?

   - [ ] Switch to a larger model and keep one agent.
   - [x] Split responsibilities into specialized agents, each with one purpose.
   - [ ] Remove tools to shorten the prompt.
   - [ ] Continue with the current design; complexity is expected.

3. What is the key difference between the routing and orchestrator-worker flow patterns?

   - [ ] Routing decomposes a task into parallel subtasks; orchestrator-worker picks one handler.
   - [ ] They are interchangeable names for the same pattern.
   - [x] Routing selects one path for the request; orchestrator-worker splits one job into multiple subtasks and merges the results.
   - [ ] Routing requires a checkpointer; orchestrator-worker does not.

4. Why is a ToolNode preferred over a manual tool-dispatch loop in LangGraph?

   - [ ] It makes model calls faster by skipping the model entirely.
   - [x] It packages tool lookup, execution, error capture, and writing results back into state into one prebuilt node.
   - [ ] It removes the need for a model in the graph.
   - [ ] It stores tool results in a database automatically.

5. How should a tool access the current user's `account_tier` stored in graph state?

   - [ ] Add `account_tier` as a normal tool argument so the model passes it in.
   - [x] Declare a `runtime: ToolRuntime` parameter and read `runtime.state["account_tier"]`.
   - [ ] Import the global graph object and read its `.state` attribute directly.
   - [ ] Parse the value out of the conversation history inside the tool.

6. Why should a tool read only the specific state keys it depends on instead of the full conversation history?

   - [ ] Reading full history is impossible in LangGraph.
   - [x] It keeps each tool scoped and efficient: less context bloat, lower latency, and no coupling to unrelated state.
   - [ ] The full history is encrypted and cannot be read by tools.
   - [ ] Tools are not allowed to read state at all.

[Ask Rigo about designing multi-agent systems in LangGraph](https://4geeks.com/ask?query=how-to-design-multi-agent-systems-in-langgraph)
