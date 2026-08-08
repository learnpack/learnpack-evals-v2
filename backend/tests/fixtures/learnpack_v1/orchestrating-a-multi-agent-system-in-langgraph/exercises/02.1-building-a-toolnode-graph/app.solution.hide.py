from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic

@tool
def get_weather(city: str) -> str:
    return f"It is 22°C and sunny in {city}."

llm = ChatAnthropic(model="claude-sonnet-5")
llm_with_tools = llm.bind_tools([get_weather])

def call_model(state: MessagesState) -> dict:
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("model", call_model)
builder.add_node("tools", ToolNode([get_weather]))
builder.add_edge(START, "model")
builder.add_conditional_edges("model", tools_condition)
builder.add_edge("tools", "model")
graph = builder.compile()

result = graph.invoke({"messages": [{"role": "user", "content": "Weather in Paris?"}]})
print(result["messages"][-1].content)
