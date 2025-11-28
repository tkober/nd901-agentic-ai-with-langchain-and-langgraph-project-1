#### ND901 - Agentic AI Engineer with LangChain and LangGraph

# Project 1: Report Building Agent


## Prerequisites

This project is set up on top of the python tooling of [Astral.sh](https://astral.sh/), escpecially their package manager `uv`. If you have it already installed you can set up this project and install all dependencies by running the following command inside the root folder.

```
uv sync
``` 

## Running the Agent

After synchronizing your [pyproject.toml](pyproject.toml) as shown above you can run the agent on your terminal from the project root by simply running the [main.py](main.py)

```
python main.py
``` 

## Example Run


![](doc/conversation.png)

```
[
  {
    "timestamp": "2025-11-22T23:24:33.270411",
    "tool_name": "solve_expression",
    "input": {
      "expression": "4+5"
    },
    "output": "{'result': 9}"
  },
  {
    "timestamp": "2025-11-22T23:24:59.493174",
    "tool_name": "document_reader",
    "input": {
      "doc_id": "INV-001"
    },
    "output": "{'found': True, 'doc_type': 'invoice'}"
  },
  {
    "timestamp": "2025-11-22T23:25:00.181028",
    "tool_name": "solve_expression",
    "input": {
      "expression": "20000 + 2000"
    },
    "output": "{'result': 22000}"
  },
  {
    "timestamp": "2025-11-22T23:25:20.853692",
    "tool_name": "document_search",
    "input": {
      "query": "contracts",
      "search_type": "type",
      "doc_type": "contract",
      "min_amount": null,
      "max_amount": null,
      "comparison": null,
      "amount": null
    },
    "output": "{'results_count': 1}"
  },
  {
    "timestamp": "2025-11-22T23:25:21.671022",
    "tool_name": "document_reader",
    "input": {
      "doc_id": "CON-001"
    },
    "output": "{'found': True, 'doc_type': 'contract'}"
  }
]
```

## Architecture

![alt text](doc/langgraph_agent_architecture.png)

## Memory



## Design Decisions
