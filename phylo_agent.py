import json
import re
import requests
import time
from pathlib import Path

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "llama3.1:8b"

KNOWLEDGE_FILE = (
    Path(__file__).resolve().parent
    / "knowledge"
    / "hp2net_knowledge.json"
)

SYSTEM_PROMPT = """
You are a scientific workflow planner for HP2Net.

Your task is to translate a user's scientific request into the complete sequence
of software tools required to achieve that request, using only the workflows
and tools provided in HP2Net knowledge.

IMPORTANT:
You MUST return exactly one JSON object.
You MUST NOT wrap the JSON in Markdown or ```json fences.

Required JSON format:
{
  "goal": "short description of the user request",
  "steps": ["tool_1", "tool_2", "tool_3"]
}

Rules:
1. "steps" must contain ONLY tool names in execution order.
2. The steps must represent the COMPLETE workflow required to achieve the user's goal.
3. If the user mentions the beginning and end of a workflow, infer and include
   any intermediate tools required by a relevant implemented HP2Net workflow.
4. Do NOT omit intermediate tools merely because the user did not explicitly
   mention them.
5. Use the workflow descriptions and workflow step sequences provided in the
   HP2Net knowledge as the authoritative source for intermediate steps.
6. Do not invent tools. Use only tools mentioned in HP2Net knowledge.
7. Do not infer execution status, implementation status, or validation results.
8. Preserve the exact tool names used in HP2Net knowledge.

Example:
If the knowledge contains:

MrBayes -> MBSUM -> BUCKy -> Quartet MaxCut -> SNaQ

and the user requests:

"Use MrBayes to infer Bayesian gene trees and then infer a network with SNaQ."

the correct steps are:

["MrBayes", "MBSUM", "BUCKy", "Quartet MaxCut", "SNaQ"]

not:

["MrBayes", "SNaQ"]
"""

def load_knowledge():
    if not KNOWLEDGE_FILE.exists():
        raise FileNotFoundError(
            f"Knowledge file not found: {KNOWLEDGE_FILE}"
        )

    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize_text(text):
    text = text.lower()

    replacements = {
        "iq-tree": "iqtree",
        "iq tree": "iqtree",
        "iqtree2": "iqtree",
        "phylo-net": "phylonet",
        "phylo net": "phylonet",
        "mr bayes": "mrbayes",
        "mr-bayes": "mrbayes",
        "maximum pseudo likelihood": "mpl",
        "maximum pseudo-likelihood": "mpl",
        "maximum parsimony": "mp"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text

def detect_tools(query, knowledge):
    normalized_query = normalize_text(query)
    detected = []

    for tool_name in knowledge["tools"]:
        normalized_tool = normalize_text(tool_name)
        pattern = r"\b" + re.escape(normalized_tool) + r"\b"
        if re.search(pattern, normalized_query):
            detected.append(tool_name)

    return detected

def select_knowledge(query, knowledge):
    detected_tools = detect_tools(query, knowledge)

    selected_tools = {
        tool: knowledge["tools"][tool]
        for tool in detected_tools
        if tool in knowledge["tools"]
    }

    selected_workflows = {}
    workflows = knowledge.get("workflows", {})

    for workflow_name, workflow in workflows.items():
        workflow_steps = workflow.get("steps", [])
        if any(tool in detected_tools for tool in workflow_steps):
            selected_workflows[workflow_name] = workflow

    return {
        "tools": selected_tools,
        "workflows": selected_workflows
    }

def build_context(selected_knowledge):
    context_parts = []
    tools = selected_knowledge["tools"]
    workflows = selected_knowledge["workflows"]

    if tools:
        context_parts.append("AVAILABLE TOOLS:")
        for name, tool in tools.items():
            line = f"- {name}: {tool.get('role', '')}"
            if "method" in tool:
                line += f"; method={tool['method']}"
            context_parts.append(line)

    if workflows:
        if context_parts:
            context_parts.append("")
        context_parts.append("RELEVANT IMPLEMENTED WORKFLOWS:")
        context_parts.append(
            "The following workflow sequences are complete operational sequences. "
            "When a user's request matches the beginning and end of one of these "
            "workflows, include all intermediate tools."
        )
        for name, workflow in workflows.items():
            steps = " -> ".join(workflow.get("steps", []))
            context_parts.append(f"- {name}: {steps}")
            if workflow.get("description"):
                context_parts.append(f"  {workflow['description']}")

    return "\n".join(context_parts)

def build_prompt(user_query, selected_knowledge):
    context = build_context(selected_knowledge)

    return f"""
User request:
{user_query}

{context}

Determine the steps (tools) required for this request and return ONLY the JSON object.
"""

def call_ollama(user_prompt):
    payload = {
        "model": MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\nUSER REQUEST:\n{user_prompt}",
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "top_p": 0.9,
            "num_ctx": 4096,
            "num_predict": 512
        }
    }

    start = time.time()
    response = requests.post(OLLAMA_URL, json=payload, timeout=300)
    response.raise_for_status()

    data = response.json()
    print(f"\nOllama generation time: {time.time() - start:.1f} s")

    return data.get("response", "")

def parse_response(response_text):
    if not response_text or not response_text.strip():
        raise RuntimeError("LLM returned an empty response.")

    if "</think>" in response_text:
        response_text = response_text.split("</think>")[-1].strip()

    match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not match:
        raise RuntimeError(f"No JSON object found in response:\n{response_text}")

    json_str = match.group(0)

    try:
        raw_json = json.loads(json_str)
        return raw_json
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON: {e}\nString: {json_str}")

def validate_interfaces(steps, knowledge):
    """
    Validate consecutive workflow steps against known interfaces.
    """
    interfaces = knowledge.get("interfaces", [])

    for producer, consumer in zip(steps, steps[1:]):
        matching = [
            interface
            for interface in interfaces
            if interface["producer"] == producer and interface["consumer"] == consumer
        ]

        if not matching:
            return False, f"No interface found for {producer} -> {consumer}."

        if not matching[0].get("supported", False):
            return False, matching[0].get(
                "reason",
                f"{producer} -> {consumer} is unsupported."
            )

    return True, None

def validate_composition(steps, knowledge):
    """
    Validate a proposed workflow against implemented workflows,
    supported compositions, and interface capabilities.
    """
    requested_steps = list(steps)

    valid_interfaces, interface_reason = validate_interfaces(
        steps,
        knowledge
    )

    # 1. Check exact implemented workflows.
    for workflow_name, workflow in knowledge.get("workflows", {}).items():

        workflow_steps = workflow.get("steps", [])

        if requested_steps == workflow_steps:

            implemented = (
                workflow.get("implemented", False)
                and valid_interfaces
            )

            notes = []

            if implemented:
                notes.append(
                    f"Implemented as part of {workflow_name}."
                )

            if not valid_interfaces and interface_reason:
                notes.append(interface_reason)

            return {
                "status": "existing_workflow",
                "execution_status": (
                    "implemented"
                    if implemented
                    else "uncertain"
                ),
                "implementation_notes": notes
            }

    # 2. Check supported compositions.
    for composition in knowledge.get("supported_compositions", []):

        supported_steps = composition.get("steps", [])

        if requested_steps == supported_steps:

            implemented = (
                composition.get("implemented", False)
                and valid_interfaces
            )

            notes = []

            part_of = composition.get("implemented_as_part_of")

            if part_of:
                notes.append(
                    f"Implemented as part of {part_of}."
                )

            if not valid_interfaces and interface_reason:
                notes.append(interface_reason)

            return {
                "status": "existing_workflow",
                "execution_status": (
                    "implemented"
                    if implemented
                    else "uncertain"
                ),
                "implementation_notes": notes
            }

    # 3. No exact implemented composition was found.
    notes = []

    if interface_reason:
        notes.append(interface_reason)

    return {
        "status": "new_workflow",
        "execution_status": "uncertain",
        "implementation_notes": notes
    }

def validate_plan(plan):
    required_keys = {
        "status",
        "execution_status",
        "goal",
        "workflow_name",
        "steps",
        "implementation_notes"
    }

    missing = required_keys - set(plan.keys())
    if missing:
        raise ValueError(f"Missing required fields: {sorted(missing)}")

    extra = set(plan.keys()) - required_keys
    if extra:
        raise ValueError(f"Unexpected fields: {sorted(extra)}")

    if not isinstance(plan["steps"], list) or not plan["steps"]:
        raise ValueError("'steps' must be a non-empty list.")

def main():
    user_query = input("What workflow do you want to construct?\n> ").strip()

    if not user_query:
        raise ValueError("The workflow request cannot be empty.")

    print("\nLoading HP2Net knowledge...")
    knowledge = load_knowledge()

    selected_knowledge = select_knowledge(user_query, knowledge)

    prompt = build_prompt(user_query, selected_knowledge)

    print("\nQuerying LLM for step proposal...")
    raw_response = call_ollama(prompt)

    llm_output = parse_response(raw_response)

    steps = llm_output.get("steps", [])
    goal = llm_output.get("goal", "Construct requested workflow")
    workflow_name = "-".join(steps) if steps else "Unnamed-Workflow"

    print("\nValidating proposed steps via Python logic...")
    validation = validate_composition(steps, knowledge)

    plan = {
        "status": validation["status"],
        "execution_status": validation["execution_status"],
        "goal": goal,
        "workflow_name": workflow_name,
        "steps": steps,
        "implementation_notes": validation["implementation_notes"]
    }

    validate_plan(plan)

    print("\n" + "=" * 70)
    print("FINAL VALIDATED WORKFLOW PLAN")
    print("=" * 70)
    print(json.dumps(plan, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()