"""
phylo_agent.py
=================
Scientific workflow planning agent for HP2Net. Translates natural language user requests into validated sequences of bioinformatics tool executions using local LLM generation coupled with deterministic Python validation logic.
"""

import json
import re
import requests
import time
from pathlib import Path

OLLAMA_API_ENDPOINT = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.1:8b"

KNOWLEDGE_BASE_PATH = (
    Path(__file__).resolve().parent
    / "knowledge"
    / "hp2net_knowledge.json"
)

SYSTEM_PROMPT = """
You are a scientific workflow planner for HP2Net.

Your task is to translate a user's scientific request into the complete sequence of software tools required to satisfy that request, using only the workflows and tools provided in HP2Net knowledge.

IMPORTANT:
You MUST return exactly one JSON object.
You MUST NOT wrap the JSON in Markdown or ```json fences.

Required JSON format:
{
  "goal": "short description of the user request",
  "steps": ["tool_1", "tool_2", "tool_3"]
}

IMPORTANT DISTINCTION:

The user's request defines the required endpoints of the workflow.

You may infer missing intermediate tools only between tools explicitly requested by the user. Never add tools before the first requested tool or after the last requested tool.

A longer implemented workflow must not be used to extend the user's request beyond its stated endpoints.

For example:

User: "Infer gene trees with RAxML and then root the resulting gene trees."
Correct:
["RAxML", "root_tree"]

Incorrect:
["RAxML", "root_tree", "PhyloNet"]

User: "Root the gene trees and then use PhyloNet to infer a phylogenetic network."
Correct:
["root_tree", "PhyloNet"]

Do not substitute or add downstream tools merely because they appear in a longer implemented workflow.

Rules:
1. "steps" must contain ONLY tool names in execution order.
2. The steps must represent the complete sequence of tools required to satisfy the user's stated request.
3. If the user explicitly specifies two tools as the start and end of the requested sequence, infer intermediate tools only if they are required to connect those tools in an implemented or supported HP2Net composition.
4. Do NOT omit intermediate tools merely because the user did not explicitly mention them.
5. Use the workflow descriptions and workflow step sequences provided in the HP2Net knowledge as the authoritative source for intermediate steps.
6. Do not invent tools. Use only tools mentioned in HP2Net knowledge.
7. Do not infer execution status, implementation status, or validation results.
8. Preserve the exact tool names used in HP2Net knowledge.
9. Do not add tools merely to complete an implemented workflow if those tools were not required by the user's request or by a supported composition connecting the requested endpoints.
10. Preserve the endpoints specified by the user. Do not add tools after the requested endpoint or before the requested starting tool.
11. Intermediate tools may be inferred only when they are required to connect the requested tools within an implemented or supported workflow composition.
12. If the requested combination is not supported by any implemented workflow or supported composition, do not force it into an existing workflow. Return the requested tools in the order implied by the user's request and let the Python validation determine whether the composition is supported.
13. Do not infer missing upstream tools. For example, if the user asks to root gene trees and then use PhyloNet, do not automatically add RAxML or IQ-TREE unless the user specifies the gene-tree inference method.

Example of completing intermediate steps:

If the user requests:
"Use RAxML to infer gene trees and then infer a network with SNaQ."

and HP2Net provides the implemented sequence:
RAxML -> ASTRAL -> SNaQ

the correct steps are:
["RAxML", "ASTRAL", "SNaQ"]

Do not return:
["RAxML", "SNaQ"]

The intermediate tool is required to connect the requested endpoints.

Example of preserving the requested endpoint:

If the user requests:
"Use RAxML to infer gene trees and then root the resulting gene trees."

the correct steps are:
["RAxML", "root_tree"]

Do not extend the sequence with tools that occur after root_tree in a longer implemented workflow.

Example of preserving a missing upstream step:

If the user requests:
"Root the gene trees and then use PhyloNet to infer a phylogenetic network."

the correct steps are:
["root_tree", "PhyloNet"]

Do not add RAxML or IQ-TREE because they occur before root_tree in an
implemented workflow.
"""

def read_knowledge_base():
    """Load and parse the JSON knowledge base file for HP2Net.
    Input:
        None.
    Output:
        dict: Parsed HP2Net knowledge base.
    Raises:
        FileNotFoundError: If the knowledge base file does not exist.
    """
    if not KNOWLEDGE_BASE_PATH.exists():
        raise FileNotFoundError(f"Knowledge file not found: {KNOWLEDGE_BASE_PATH}")
    with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as file_stream:
        return json.load(file_stream)

def normalize_string(raw_text):
    """Normalize text and standardize known tool name variants.
    Input:
        raw_text (str): User text or tool names to normalize.

    Output:
        str: Normalized text with standardized terminology.
    """
    lowercased_text = raw_text.lower()
    replacements = {
        ("iq-tree", "iq tree", "iqtree2", "iq-tree2", "iq tree 2"): "iqtree",
        ("phylo-net", "phylo net"): "phylonet",
        ("mr bayes", "mr-bayes"): "mrbayes",
        ("maximum pseudo likelihood", "maximum pseudo-likelihood"): "mpl",
        ("maximum parsimony",): "mp"
    }
    for variants, canonical_form in replacements.items():
        for variant in variants:
            lowercased_text = lowercased_text.replace(variant, canonical_form)
    return lowercased_text

def canonicalize_tool_names(proposed_steps, knowledge_base):
    """Map tool-name variants in an LLM workflow proposal to canonical HP2Net names.
    Input:
        proposed_steps (list[str]): Tool names proposed by the LLM.
        knowledge_base (dict): HP2Net knowledge base containing canonical tool names.
    Output:
        list[str]: Workflow steps using canonical HP2Net tool names.
    """
    canonical_tools = knowledge_base.get("tools", {})
    canonical_by_normalized_name = {
        normalize_string(tool_name): tool_name
        for tool_name in canonical_tools
    }
    canonical_steps = []
    for proposed_tool in proposed_steps:
        normalized_tool = normalize_string(proposed_tool)
        if normalized_tool in canonical_by_normalized_name:
            canonical_steps.append(canonical_by_normalized_name[normalized_tool])
        else:
            canonical_steps.append(proposed_tool)
    return canonical_steps

def identify_mentioned_tools(user_query, knowledge_base):
    """Identify HP2Net tools explicitly mentioned in a user query.
    Input:
        user_query (str): Natural language workflow request.
        knowledge_base (dict): HP2Net knowledge base containing tool definitions.
    Output:
        list[str]: Tool names detected in the query, using the canonical
        names defined in the knowledge base.
    """
    normalized_query = normalize_string(user_query)
    detected_tool_names = []
    for tool_name in knowledge_base["tools"]:
        normalized_tool_name = normalize_string(tool_name)
        regex_pattern = r"\b" + re.escape(normalized_tool_name) + r"\b"
        if re.search(regex_pattern, normalized_query):
            detected_tool_names.append(tool_name)
    return detected_tool_names

def filter_relevant_knowledge(user_query, knowledge_base):
    """Extract knowledge relevant to the tools mentioned in a user query.
    Input:
        user_query (str): Natural language workflow request.
        knowledge_base (dict): HP2Net knowledge base.
    Output:
        dict: Filtered knowledge containing relevant tools and workflows.
    """
    detected_tools = identify_mentioned_tools(user_query, knowledge_base)
    selected_tools = {
        tool: knowledge_base["tools"][tool]
        for tool in detected_tools
        if tool in knowledge_base["tools"]
    }
    selected_workflows = {}
    available_workflows = knowledge_base.get("workflows", {})
    for workflow_name, workflow_data in available_workflows.items():
        execution_steps = workflow_data.get("steps", [])
        if any(tool in detected_tools for tool in execution_steps):
            selected_workflows[workflow_name] = workflow_data
    return {
        "tools": selected_tools,
        "workflows": selected_workflows
    }

def format_knowledge_context(filtered_knowledge):
    """Format filtered knowledge for inclusion in the LLM prompt.
    Input:
        filtered_knowledge (dict): Relevant tools and workflows extracted from the HP2Net knowledge base.
    Output:
        str: Human-readable knowledge context for LLM prompt construction.
    """
    formatted_sections = []
    tools_subset = filtered_knowledge["tools"]
    workflows_subset = filtered_knowledge["workflows"]
    if tools_subset:
        formatted_sections.append("AVAILABLE TOOLS:")
        for tool_name, tool_metadata in tools_subset.items():
            entry_line = f"- {tool_name}: {tool_metadata.get('role', '')}"
            if "method" in tool_metadata:
                entry_line += f"; method={tool_metadata['method']}"
            formatted_sections.append(entry_line)
    if workflows_subset:
        if formatted_sections:
            formatted_sections.append("")
        formatted_sections.append("RELEVANT IMPLEMENTED WORKFLOWS:")
        formatted_sections.append(
            "The following workflow sequences are complete operational sequences. "
            "When a user's request matches the beginning and end of one of these "
            "workflows, include all intermediate tools."
        )
        for workflow_name, workflow_metadata in workflows_subset.items():
            step_chain = " -> ".join(workflow_metadata.get("steps", []))
            formatted_sections.append(f"- {workflow_name}: {step_chain}")
            if workflow_metadata.get("description"):
                formatted_sections.append(f"  {workflow_metadata['description']}")
    return "\n".join(formatted_sections)

def compose_llm_prompt(user_query, filtered_knowledge):
    """Construct the complete prompt sent to the workflow planning LLM.
    Input:
        user_query (str): Natural language workflow request.
        filtered_knowledge (dict): Relevant HP2Net knowledge.
    Output:
        str: Formatted prompt for LLM submission.
    """
    context_text = format_knowledge_context(filtered_knowledge)
    return f"""
User request:
{user_query}

{context_text}

Determine the steps (tools) required for this request and return ONLY the JSON object.
"""

def query_ollama_model(constructed_prompt):
    """Send a workflow planning request to the local Ollama model.
    Input:
        constructed_prompt (str): Complete prompt for the LLM.
    Output:
        str: Raw response generated by the LLM.
    Raises:
        requests.RequestException: If communication with the Ollama API fails or returns an HTTP error.
    """
    request_payload = {
        "model": MODEL_NAME,
        "prompt": f"{SYSTEM_PROMPT}\n\nUSER REQUEST:\n{constructed_prompt}",
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "top_p": 0.9,
            "num_ctx": 4096,
            "num_predict": 512
        }
    }
    execution_start_time = time.time()
    api_response = requests.post(OLLAMA_API_ENDPOINT, json=request_payload, timeout=300)
    api_response.raise_for_status()
    response_data = api_response.json()
    print(f"\nOllama generation time: {time.time() - execution_start_time:.1f} s")
    return response_data.get("response", "")

def parse_llm_json_response(raw_response_text):
    """Extract and parse the JSON workflow plan returned by the LLM.
    Input:
        raw_response_text (str): Raw LLM response containing a JSON object.
    Output:
        dict: Parsed JSON workflow plan.
    Raises:
        ValueError: If the response is empty or does not contain a valid JSON object.
        json.JSONDecodeError: If the extracted text is malformed JSON.
    """
    if not raw_response_text or not raw_response_text.strip():
        raise ValueError("LLM returned an empty response.")
    if "</think>" in raw_response_text:
        raw_response_text = raw_response_text.split("</think>")[-1].strip()
    regex_match = re.search(r"\{.*\}", raw_response_text, re.DOTALL)
    if not regex_match:
        raise ValueError(f"No JSON object found in response:\n{raw_response_text}")
    extracted_json_string = regex_match.group(0)
    return json.loads(extracted_json_string)

def check_interface_compatibility(proposed_steps, knowledge_base):
    """Check whether consecutive workflow tools have supported interfaces, validanting consecutive workflow steps against known interfaces.
    Input:
        proposed_steps (list[str]): Ordered sequence of proposed tool names.
        knowledge_base (dict): HP2Net knowledge base containing interface definitions.
    Output:
        tuple[bool, str|None]: A validation flag and an optional explanation of the first incompatible interface.
    """
    available_interfaces = knowledge_base.get("interfaces", [])
    for producer_tool, consumer_tool in zip(proposed_steps, proposed_steps[1:]):
        producer_norm = normalize_string(producer_tool)
        consumer_norm = normalize_string(consumer_tool)
        matching_interfaces = [
            interface
            for interface in available_interfaces
            if normalize_string(interface["producer"]) == producer_norm
            and normalize_string(interface["consumer"]) == consumer_norm
        ]
        if not matching_interfaces:
            return False, f"No interface found for {producer_tool} -> {consumer_tool}."
        if not matching_interfaces[0].get("supported", False):
            return False, matching_interfaces[0].get(
                "reason",
                f"{producer_tool} -> {consumer_tool} is unsupported."
            )
    return True, None

def evaluate_workflow_composition(proposed_steps, knowledge_base):
    """Evaluate a proposed workflow against HP2Net capabilities. The evaluation checks tool validity, interfaces, implemented workflows, supported compositions, and valid subsequences of implemented workflows.
    Input:
        proposed_steps (list[str]): Ordered sequence of proposed tools.
        knowledge_base (dict): HP2Net knowledge base.
    Output:
        dict: Evaluation result containing workflow status, execution status, and implementation notes.
    """
    requested_step_sequence = list(proposed_steps)
    known_tool_registry = set(knowledge_base.get("tools", {}).keys())
    unrecognized_tools = [tool for tool in requested_step_sequence if tool not in known_tool_registry]
    if unrecognized_tools:
        return {
            "status": "invalid_workflow",
            "execution_status": "unsupported",
            "implementation_notes": [
                f"Unknown tool(s): {', '.join(unrecognized_tools)}."
            ]
        }
    has_valid_interfaces, interface_error_reason = check_interface_compatibility(proposed_steps, knowledge_base)
    for workflow_name, workflow_metadata in knowledge_base.get("workflows", {}).items():
        defined_workflow_steps = workflow_metadata.get("steps", [])
        if requested_step_sequence == defined_workflow_steps:
            is_implemented = workflow_metadata.get("implemented", False) and has_valid_interfaces
            validation_notes = []
            if is_implemented:
                validation_notes.append(f"Implemented as part of {workflow_name}.")
            if not has_valid_interfaces and interface_error_reason:
                validation_notes.append(interface_error_reason)
            return {
                "status": "existing_workflow",
                "execution_status": "implemented" if is_implemented else "uncertain",
                "implementation_notes": validation_notes
            }
    for composition_metadata in knowledge_base.get("supported_compositions", []):
        supported_step_sequence = composition_metadata.get("steps", [])
        if requested_step_sequence == supported_step_sequence:
            is_implemented = composition_metadata.get("implemented", False) and has_valid_interfaces
            validation_notes = []
            parent_workflow = composition_metadata.get("implemented_as_part_of")
            if parent_workflow:
                validation_notes.append(f"Implemented as part of {parent_workflow}.")
            if not has_valid_interfaces and interface_error_reason:
                validation_notes.append(interface_error_reason)
            return {
                "status": "existing_composition",
                "execution_status": "implemented" if is_implemented else "uncertain",
                "implementation_notes": validation_notes
            }
    for workflow_name, workflow_metadata in knowledge_base.get("workflows", {}).items():
        defined_workflow_steps = workflow_metadata.get("steps", [])
        for offset in range(len(defined_workflow_steps) - len(requested_step_sequence) + 1):
            if defined_workflow_steps[offset:offset + len(requested_step_sequence)] == requested_step_sequence:
                is_implemented = workflow_metadata.get("implemented", False) and has_valid_interfaces
                validation_notes = [f"Implemented as part of {workflow_name}."]
                if not has_valid_interfaces and interface_error_reason:
                    validation_notes.append(interface_error_reason)
                return {
                    "status": "existing_composition",
                    "execution_status": "implemented" if is_implemented else "uncertain",
                    "implementation_notes": validation_notes
                }
    if has_valid_interfaces:
        return {
            "status": "new_supported_workflow",
            "execution_status": "not_implemented",
            "implementation_notes": [
                "Valid and supported tool sequence, but not yet implemented in parsl_workflow.py."
            ]
        }
    validation_notes = []
    if interface_error_reason:
        validation_notes.append(interface_error_reason)
    return {
        "status": "unsupported_composition",
        "execution_status": "unsupported",
        "implementation_notes": validation_notes
    }

def verify_plan_structure(plan_dictionary):
    """Validate the structure and data types of a final workflow plan.
    Input:
        plan_dictionary (dict): Final workflow plan to validate.
    Output:
        None.
    Raises:
        ValueError: If required fields are missing, unexpected fields are present, or the steps field is invalid.
    """
    mandatory_keys = {
        "status",
        "execution_status",
        "goal",
        "workflow_name",
        "steps",
        "implementation_notes"
    }
    missing_keys = mandatory_keys - set(plan_dictionary.keys())
    if missing_keys:
        raise ValueError(f"Missing required fields: {sorted(missing_keys)}")
    unexpected_keys = set(plan_dictionary.keys()) - mandatory_keys
    if unexpected_keys:
        raise ValueError(f"Unexpected fields: {sorted(unexpected_keys)}")
    if not isinstance(plan_dictionary["steps"], list) or not plan_dictionary["steps"]:
        raise ValueError("'steps' must be a non-empty list.")

def main():
    user_query = input("What workflow do you want to construct?\n> ").strip()
    if not user_query:
        raise ValueError("The workflow request cannot be empty.")
    print("\nLoading HP2Net knowledge...")
    knowledge_base = read_knowledge_base()
    filtered_knowledge = filter_relevant_knowledge(user_query, knowledge_base)
    constructed_prompt = compose_llm_prompt(user_query, filtered_knowledge)
    print("\nQuerying LLM for step proposal...")
    raw_llm_output = query_ollama_model(constructed_prompt)
    parsed_llm_output = parse_llm_json_response(raw_llm_output)
    proposed_steps = parsed_llm_output.get("steps", [])
    proposed_steps = canonicalize_tool_names(proposed_steps, knowledge_base)
    workflow_goal = parsed_llm_output.get("goal", "Construct requested workflow")
    workflow_identifier = "-".join(proposed_steps) if proposed_steps else "Unnamed-Workflow"
    print("\nValidating proposed steps via Python logic...")
    composition_evaluation = evaluate_workflow_composition(proposed_steps, knowledge_base)
    final_plan = {
        "status": composition_evaluation["status"],
        "execution_status": composition_evaluation["execution_status"],
        "goal": workflow_goal,
        "workflow_name": workflow_identifier,
        "steps": proposed_steps,
        "implementation_notes": composition_evaluation["implementation_notes"]
    }
    verify_plan_structure(final_plan)
    print("\n" + "=" * 70)
    print("FINAL VALIDATED WORKFLOW PLAN")
    print("=" * 70)
    print(json.dumps(final_plan, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()