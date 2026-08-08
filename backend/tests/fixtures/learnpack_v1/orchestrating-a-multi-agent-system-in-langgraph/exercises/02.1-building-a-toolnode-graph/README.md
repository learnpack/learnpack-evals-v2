---
readingTime:
  minutes: 0.72
  words: 180
fkglResult: 9.0
---

# 02.1 Building a ToolNode Graph

You've seen how a `ToolNode` replaces a hand-written tool-dispatch loop; now you'll wire one into a working agent graph. In this challenge you'll assemble a `StateGraph` where the model decides when to call a tool, a `ToolNode` runs it, and the result flows back to the model.

**Your task:** complete the graph in `app.py` so the agent loop runs end to end.

- Build a `StateGraph` over `MessagesState` with a `"model"` node (the provided `call_model` function) and a `"tools"` node that runs the `get_weather` tool through a `ToolNode`.
- Wire the loop: an edge from `START` into `"model"`, a conditional edge out of `"model"` using the prebuilt `tools_condition`, and an edge from `"tools"` back to `"model"`.
- Compile the graph and invoke it with a weather question.

**Expected result:** asking "Weather in Paris?" makes the model call `get_weather`, the `ToolNode` runs it, and the model returns a final answer that includes the weather.
