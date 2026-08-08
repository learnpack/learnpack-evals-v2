from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.tools import tool
from langchain_anthropic import ChatAnthropic

@tool
def get_weather(city: str) -> str:
    return f"It is 22°C and sunny in {city}."

llm = ChatAnthropic(model="claude-sonnet-5")
llm_with_tools = llm.bind_tools([get_weather])

# Define the model invocation function
# This function should take the current state and return updated messages
# TODO: Complete the function implementation

def call_model(state: MessagesState) -> dict:
    # This is a placeholder implementation
    return {"messages": state["messages"]}

# Build the StateGraph
# TODO: Initialize the builder, add nodes, wire edges, compile the graph

# builder = ...

# Invoke the graph with an initial message
# TODO: Run the graph and print the final response

