from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal

from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain.agents import create_agent
from langgraph.prebuilt import tools_condition, ToolNode
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
import re
import operator
from schemas import (
    UserIntent,
    SessionState,
    AnswerResponse,
    SummarizationResponse,
    CalculationResponse,
    UpdateMemoryResponse,
)
from prompts import (
    get_intent_classification_prompt,
    get_chat_prompt_template,
    MEMORY_SUMMARY_PROMPT,
)


# The AgentState class is already implemented for you.  Study the
# structure to understand how state flows through the LangGraph
# workflow.  See README.md Task 2.1 for detailed explanations of
# each property.
class AgentState(TypedDict, total=False):
    """
    The agent state object
    """

    # Current conversation
    user_input: Optional[str]
    messages: Annotated[List[BaseMessage], add_messages]

    # Intent and routing
    intent: Optional[UserIntent]
    next_step: str

    # Memory and context
    conversation_summary: str
    active_documents: Optional[List[str]]

    # Current task state
    current_response: Optional[Dict[str, Any]]
    tools_used: List[str]

    # Session management
    session_id: Optional[str]
    user_id: Optional[str]

    # Modify actions_taken to use an operator.add reducer
    actions_taken: Annotated[List[str], operator.add]


def invoke_react_agent(
    response_schema: type[BaseModel], messages: List[BaseMessage], llm, tools
) -> tuple[Dict[str, Any], List[str]]:
    llm_with_tools = llm.bind_tools(tools)
    agent = create_agent(
        model=llm_with_tools,  # Use the bound model
        tools=tools,
        response_format=response_schema,
    )

    result = agent.invoke({"messages": messages})
    tools_used = [
        t.name for t in result.get("messages", []) if isinstance(t, ToolMessage)
    ]

    return result, tools_used


# Implement the classify_intent function.
# This function should classify the user's intent and set the next step in the workflow.
# Refer to README.md Task 2.2
def classify_intent(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Classify user intent and update next_step. Also records that this
    function executed by appending "classify_intent" to actions_taken.
    """

    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        raise TypeError("Expected 'configurable' to be a dictionary.")
    llm = configurable.get("llm")
    if not isinstance(llm, ChatOpenAI):
        raise TypeError("Expected 'llm' to be of type ChatOpenAI.")
    history = state.get("messages", [])

    # Configure the llm chat model for structured output
    structured_output_llm = llm.with_structured_output(UserIntent)

    # Create a formatted prompt with conversation history and user input
    prompt = get_intent_classification_prompt().format(
        user_input=state["user_input"], conversation_history=history
    )

    result: UserIntent = structured_output_llm.invoke(prompt)

    # Add conditional logic to set next_step based on intent
    next_step = {
        "qa": "qa_agent",
        "summarization": "summarization_agent",
        "calculation": "calculation_agent",
        "unknown": "qa_agent",
    }[result.intent_type]

    return AgentState(
        actions_taken=["classify_intent"],
        intent=result,
        next_step=next_step,
    )


def qa_agent(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Handle Q&A tasks and record the action.
    """
    configurable = config.get("configurable") or {}
    llm = configurable.get("llm")
    tools = configurable.get("tools")

    prompt_template = get_chat_prompt_template("qa")

    messages = prompt_template.invoke(
        {
            "input": state["user_input"],
            "chat_history": state.get("messages", []),
        }
    ).to_messages()

    result, tools_used = invoke_react_agent(AnswerResponse, messages, llm, tools)

    return {
        "messages": result.get("messages", []),
        "actions_taken": ["qa_agent"],
        "current_response": result,
        "tools_used": tools_used,
        "next_step": "update_memory",
    }


# Implement the summarization_agent function. Refer to README.md Task 2.3
def summarization_agent(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Handle summarization tasks and record the action.
    """
    configurable = config.get("configurable") or {}
    llm = configurable.get("llm")
    tools = configurable.get("tools")

    prompt_template = get_chat_prompt_template("summarization")

    messages = prompt_template.invoke(
        {
            "input": state["user_input"],
            "chat_history": state.get("messages", []),
        }
    ).to_messages()

    result, tools_used = invoke_react_agent(SummarizationResponse, messages, llm, tools)

    return {
        "messages": result.get("messages", []),
        "actions_taken": ["summarization_agent"],
        "current_response": result,
        "tools_used": tools_used,
        "next_step": "update_memory",
    }


# Implement the calculation_agent function. Refer to README.md Task 2.3
def calculation_agent(state: AgentState, config: RunnableConfig) -> AgentState:
    configurable = config.get("configurable") or {}
    llm = configurable.get("llm")
    tools = configurable.get("tools")

    prompt_template = get_chat_prompt_template("calculation")

    messages = prompt_template.invoke(
        {
            "input": state["user_input"],
            "chat_history": state.get("messages", []),
        }
    ).to_messages()

    result, tools_used = invoke_react_agent(CalculationResponse, messages, llm, tools)

    return {
        "messages": result.get("messages", []),
        "actions_taken": ["calculation_agent"],
        "current_response": result,
        "tools_used": tools_used,
        "next_step": "update_memory",
    }


# Finish implementing the update_memory function. Refer to README.md Task 2.4
def update_memory(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Update conversation memory and record the action.
    """

    # Retrieve the LLM from config
    configurable = config.get("configurable") or {}
    llm = configurable.get("llm")

    prompt_with_history = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(MEMORY_SUMMARY_PROMPT),
            MessagesPlaceholder("chat_history"),
        ]
    ).invoke(
        {
            "chat_history": state.get("messages", []),
        }
    )

    structured_llm = llm.with_structured_output(
        # Pass in the correct schema from scheams.py to extract conversation summary, active documents
        UpdateMemoryResponse
    )

    response: UpdateMemoryResponse = structured_llm.invoke(prompt_with_history)

    return AgentState(
        conversation_summary=response.summary,
        active_documents=response.document_ids,
        next_step="END",
    )


def should_continue(state: AgentState) -> str:
    """Router function"""
    return state.get("next_step", "end")


# Complete the create_workflow function. Refer to README.md Task 2.5
def create_workflow(llm, tools):
    """
    Creates the LangGraph agents.
    Compiles the workflow with an InMemorySaver checkpointer to persist state.
    """
    workflow = StateGraph(AgentState)

    # Add all the nodes to the workflow by calling workflow.add_node(...)
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("qa_agent", qa_agent)
    workflow.add_node("summarization_agent", summarization_agent)
    workflow.add_node("calculation_agent", calculation_agent)
    workflow.add_node("update_memory", update_memory)

    workflow.set_entry_point("classify_intent")
    workflow.add_conditional_edges(
        "classify_intent",
        should_continue,
        {
            "qa_agent": "qa_agent",
            "summarization_agent": "summarization_agent",
            "calculation_agent": "calculation_agent",
            "end": END,
        },
    )

    # For each node add an edge that connects it to the update_memory node
    # qa_agent -> update_memory
    # summarization_agent -> update_memory
    # calculation_agent -> update_memory
    workflow.add_edge("qa_agent", "update_memory")
    workflow.add_edge("summarization_agent", "update_memory")
    workflow.add_edge("calculation_agent", "update_memory")

    workflow.add_edge("update_memory", END)

    # Modify the return values below by adding a checkpointer with InMemorySaver
    return workflow.compile(checkpointer=InMemorySaver())
