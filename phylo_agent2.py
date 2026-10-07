"""
phylo_agent2.py
===========================
Parsl Python code generator agent, backed by local Ollama LLMs, coupled with deterministic AST-based syntax and semantic validation.
"""

import ast
import json
import os
import re
import requests
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

OLLAMA_API_ENDPOINT = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.1:8b"

ORIGINAL_KB_PATH = "knowledge/hp2net_knowledge.json"
TEST_KB_PATH = "knowledge/test_knowledge.json"

IMPLEMENTATION_SPEC = {
    "framework": "Parsl",
    "workflow_file": "parsl_workflow.py",
    "output_format": "one Python function starting with def",
    "rules": [
        "Use only imports, decorators, applications and utility functions present in the implementation context.",
        "Preserve existing HP2Net resource handling and parameter passing conventions.",
        "Do not invent external APIs.",
        "Do not invent HP2Net APIs.",
        "Do not invent modules, classes, decorators or functions.",
        "Implement strictly the validated tool sequence.",
        "Do not add tools before, after, or between the validated steps."
    ]
}

def read_json_file(file_path):
    """Load and parse a JSON knowledge base.
    Input:
        file_path (str): Path to the JSON file.
    Output:
        dict: Parsed JSON content.
    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as file_stream:
        return json.load(file_stream)

def extract_available_apps(file_path="apps.py"):
    """Extract function names defined in the Parsl apps module.
    Input:
        file_path (str): Path to the Python file containing Parsl app definitions.
    Output:
        set[str]: Set of function names defined in the file.
    """
    if not os.path.exists(file_path):
        return set()
    with open(file_path, "r", encoding="utf-8") as file_stream:
        source_code = file_stream.read()
    try:
        syntax_tree = ast.parse(source_code, filename=file_path)
    except SyntaxError:
        return set()
    return {
        node.name for node in ast.walk(syntax_tree) 
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

def extract_app_signatures(file_path="apps.py"):
    """Extract function signatures, decorators, and docstrings from Parsl apps.
    Input:
        file_path (str): Path to the Python file containing Parsl app definitions.
    Output:
        str: Formatted application contracts for inclusion in the LLM prompt.
    """
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "r", encoding="utf-8") as file_stream:
        source_code = file_stream.read()
    try:
        syntax_tree = ast.parse(source_code, filename=file_path)
    except SyntaxError:
        return ""
    extracted_signatures = []
    for node in ast.walk(syntax_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = [f"@{ast.unparse(decorator)}" for decorator in node.decorator_list]
            decorator_prefix = "\n".join(decorators) + "\n" if decorators else ""
            argument_names = [arg.arg for arg in node.args.args]
            function_signature = f"{decorator_prefix}def {node.name}({', '.join(argument_names)}):"
            function_docstring = ast.get_docstring(node)
            if function_docstring:
                function_signature += f'\n    """{function_docstring.strip()}"""'
            function_signature += "\n    pass\n"
            extracted_signatures.append(function_signature)
    return f"===== AVAILABLE APPS CONTRACTS ({file_path}) =====\n" + "\n".join(extracted_signatures)

def load_apps_context():
    """Load Parsl app contracts for inclusion in the Agent 2 prompt.
    Input:
        None.
    Output:
        str: Formatted function signatures, decorators, and docstrings extracted from apps.py.
    """
    return extract_app_signatures("apps.py")

def normalize_text(raw_text):
    """Normalize tool names and related terminology for comparison.
    Input:
        raw_text (str): Tool name or text to normalize.
    Output:
        str: Lowercase normalized text with known naming variants replaced by canonical forms.: str: Normalized text string.
    """
    lowercased_text = raw_text.lower()
    replacement_mappings = {
        ("iq-tree", "iq tree", "iqtree2", "iq-tree2", "iq tree 2"): "iqtree",
        ("phylo-net", "phylo net"): "phylonet",
        ("mr bayes", "mr-bayes"): "mrbayes",
        ("maximum pseudo likelihood", "maximum pseudo-likelihood"): "mpl",
        ("maximum parsimony",): "mp"
    }
    for variant_tuple, canonical_form in replacement_mappings.items():
        for variant in variant_tuple:
            lowercased_text = lowercased_text.replace(variant, canonical_form)
    return lowercased_text

def canonicalize_tool_names(proposed_steps, knowledge_base):
    """Map proposed tool-name variants to canonical HP2Net tool names.
    Input:
        proposed_steps (list[str]): Tool sequence proposed by the LLM.
        knowledge_base (dict): HP2Net knowledge base containing canonical tool definitions.
    Output:
        list[str]: Tool sequence using canonical HP2Net names where available.
    """
    canonical_tools = knowledge_base.get("tools", {})
    canonical_by_normalized_name = {
        normalize_text(tool_name): tool_name
        for tool_name in canonical_tools
    }
    canonical_steps = []
    for proposed_tool in proposed_steps:
        normalized_tool = normalize_text(proposed_tool)
        if normalized_tool in canonical_by_normalized_name:
            canonical_steps.append(canonical_by_normalized_name[normalized_tool])
        else:
            canonical_steps.append(proposed_tool)
    return canonical_steps

def extract_requested_tools(user_prompt, knowledge):
    """Extract explicitly mentioned HP2Net tools from a user request.
    Input:
        user_prompt (str): Natural language workflow request.
        knowledge (dict): Knowledge base containing known HP2Net tools.
    Output:
        list[str]: Canonical tool names in their order of appearance.
    """
    known_tools = list(knowledge.get("tools", {}).keys())
    found_tools = []
    normalized_prompt = normalize_text(user_prompt)
    for tool in known_tools:
        normalized_tool = normalize_text(tool)
        if normalized_tool in normalized_prompt:
            position = normalized_prompt.find(normalized_tool)
            found_tools.append((position, tool))
    found_tools.sort(key=lambda x: x[0])
    dedup_tools = []
    for _, tool in found_tools:
        if not dedup_tools or dedup_tools[-1] != tool:
            dedup_tools.append(tool)
    return dedup_tools

def validate_endpoints(steps, requested_tools):
    """Validate preservation of the requested workflow endpoints (starting and ending tools).
    Input:
        steps (list[str]): Tool sequence proposed by Agent 1.
        requested_tools (list[str]): Tools explicitly requested by the user.
    Output:
        tuple[bool, str | None]: Validation status and an error message if the first or last requested tool is not preserved.
    """
    if not requested_tools:
        return True, None
    if not steps:
        return False, "Plan is empty."
    if steps[0] != requested_tools[0]:
        return False, f"First endpoint violation: expected '{requested_tools[0]}', got '{steps[0]}'."
    if steps[-1] != requested_tools[-1]:
        return False, f"Last endpoint violation: expected '{requested_tools[-1]}', got '{steps[-1]}'."
    return True, None

def validate_interfaces(steps, knowledge):
    """Validate compatibility between consecutive workflow steps.
    Input:
        steps (list[str]): Proposed ordered tool sequence.
        knowledge (dict): Knowledge base containing interface definitions.
    Output:
        tuple[bool, str | None]: Validation status and an error message if a required interface is missing or unsupported.
    """
    interfaces = knowledge.get("interfaces", [])
    for i in range(len(steps) - 1):
        producer = steps[i]
        consumer = steps[i + 1]
        producer_norm = normalize_text(producer)
        consumer_norm = normalize_text(consumer)
        match = next(
            (
                iface for iface in interfaces 
                if normalize_text(iface.get("producer", "")) == producer_norm 
                and normalize_text(iface.get("consumer", "")) == consumer_norm
            ), 
            None
        )
        if not match:
            return False, f"No interface declared between {producer} and {consumer}."
        if not match.get("supported", False):
            return False, f"Interface between {producer} and {consumer} declared but not supported."
    return True, None

def validate_composition(steps, knowledge):
    """Validate a proposed workflow against known workflows, compositions, and tools.
    Input:
        steps (list[str]): Proposed ordered tool sequence.
        knowledge (dict): Target knowledge base used for validation.
    Output:
        dict: Workflow classification containing status, execution status, and implementation notes.
    """
    requested_steps = list(steps)
    known_tools = set(knowledge.get("tools", {}).keys())
    unknown_tools = [tool for tool in requested_steps if tool not in known_tools]
    if unknown_tools:
        return {
            "status": "invalid_workflow", 
            "execution_status": "unsupported", 
            "implementation_notes": [f"Unknown tool(s): {', '.join(unknown_tools)}."]
        }
    valid_interfaces, interface_reason = validate_interfaces(requested_steps, knowledge)
    for workflow_name, workflow in knowledge.get("workflows", {}).items():
        if requested_steps == workflow.get("steps", []):
            implemented = workflow.get("implemented", False) and valid_interfaces
            notes = []
            if implemented:
                notes.append(f"Implemented as part of {workflow_name}.")
            if not valid_interfaces and interface_reason:
                notes.append(interface_reason)
            return {
                "status": "existing_workflow", 
                "execution_status": "implemented" if implemented else "uncertain", 
                "implementation_notes": notes
            }
    for composition in knowledge.get("supported_compositions", []):
        if requested_steps == composition.get("steps", []):
            implemented = composition.get("implemented", False) and valid_interfaces
            notes = []
            part_of = composition.get("implemented_as_part_of")
            if part_of:
                notes.append(f"Implemented as part of {part_of}.")
            if not valid_interfaces and interface_reason:
                notes.append(interface_reason)
            return {
                "status": "existing_composition", 
                "execution_status": "implemented" if implemented else "uncertain", 
                "implementation_notes": notes
            }
    if valid_interfaces:
        return {
            "status": "new_supported_workflow", 
            "execution_status": "not_implemented", 
            "implementation_notes": ["Valid and supported tool sequence in target KB."]
        }
    notes = [interface_reason] if interface_reason else []
    return {
        "status": "unsupported_composition", 
        "execution_status": "unsupported", 
        "implementation_notes": notes
    }

def validate_generated_code(code_str, expected_steps, apps_file="apps.py"):
    """Validate generated Python code syntactically and semantically.
    Input:
        code_str (str): Python source code generated by Agent 2.
        expected_steps (list[str]): Validated HP2Net tool sequence that the generated code must implement.
        apps_file (str): Path to the Parsl apps module.
    Output:
        tuple[bool, dict, str]: Overall validation status, individual check results, and an error message when applicable.
    """
    checks = {
        "AST": "FAILED",
        "Required tools": "FAILED",
        "No extra tools": "FAILED",
        "App symbols": "FAILED"
    }
    try:
        tree = ast.parse(code_str)
        checks["AST"] = "PASSED"
    except SyntaxError as e:
        return False, checks, f"SyntaxError: {e}"
    expected_app_calls = [step.lower().replace(" ", "_").replace("-", "_") for step in expected_steps]
    called_apps = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "apps":
                    called_apps.add(node.func.attr)
    missing_tools = [tool for tool in expected_app_calls if tool not in called_apps]
    if not missing_tools:
        checks["Required tools"] = "PASSED"
    extra_tools = [tool for tool in called_apps if tool not in expected_app_calls]
    if not extra_tools:
        checks["No extra tools"] = "PASSED"
    existing_apps = extract_available_apps(apps_file)
    non_existent = [tool for tool in called_apps if tool not in existing_apps]
    if not non_existent:
        checks["App symbols"] = "PASSED"
    all_passed = all(status == "PASSED" for status in checks.values())
    return all_passed, checks, ""

def extract_python_code(content: str) -> str:
    """Extract executable Python code from an LLM response. Strip markdown code blocks and prose comments, keeping pure Python code.
    Input:
        content (str): Raw text returned by the LLM.
    Output:
        str: Cleaned Python code.
    """
    if "```python" in content:
        content = content.split("```python")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    lines = content.splitlines()
    code_lines = []
    found_def_or_import = False
    for line in lines:
        if line.startswith("def ") or line.startswith("import ") or line.startswith("from ") or line.startswith("@"):
            found_def_or_import = True
        if found_def_or_import:
            code_lines.append(line)
    return "\n".join(code_lines).strip()

def run_agent1_planner(user_prompt, original_knowledge, requested_tools):
    """Run Agent 1 to generate an ordered HP2Net workflow plan.
    Input:
        user_prompt (str): Natural language workflow request.
        original_knowledge (dict): Original HP2Net knowledge base used by the planner.
        requested_tools (list[str]): Explicitly requested workflow endpoints.
    Output:
        dict: JSON-compatible planning result containing the workflow goal and ordered tool sequence.
    """
    system_prompt = (
        "You are an expert computational biology workflow planner for HP2Net.\n"
        "Translate the user's request into an ordered sequence of HP2Net tools.\n\n"
        f"EXPLICITLY REQUESTED TOOLS: {json.dumps(requested_tools)}\n\n"
        "HARD CONSTRAINTS:\n"
        "1. Preserve the first and last tools explicitly requested by the user.\n"
        "2. If the requested endpoints are not directly connected, find a valid path between them using the original HP2Net knowledge base.\n"
        "3. Insert ONLY intermediate tools that are required by a valid interface, supported composition, or implemented workflow in the original KB.\n"
        "4. Do NOT replace either requested endpoint.\n"
        "5. Do NOT add tools before the first requested tool or after the last requested tool.\n"
        "6. If EXPLICITLY REQUESTED TOOLS has only 1 item, output EXACTLY that 1 item.\n"
        "7. If no valid path connects the endpoints in the original KB, output only the requested tools as steps.\n\n"
        "EXAMPLE:\n"
        "If the user requests BUCKy and SNaQ (endpoints: ['BUCKy', 'SNaQ']) and the original KB defines\n"
        "the chain BUCKy -> Quartet MaxCut -> SNaQ, output:\n"
        "[\"BUCKy\", \"Quartet MaxCut\", \"SNaQ\"]\n\n"
        f"Available original HP2Net knowledge:\n{json.dumps(original_knowledge, indent=2)}\n\n"
        "Output JSON with keys 'goal' (string) and 'steps' (list of strings)."
    )
    payload = {
        "model": MODEL_NAME,
        "prompt": f"System: {system_prompt}\nUser request: {user_prompt}",
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": 4096,
            "num_predict": 512
        }
    }
    try:
        response = requests.post(OLLAMA_API_ENDPOINT, json=payload, timeout=300)
        response.raise_for_status()
        raw_text = response.json().get("response", "").strip()
        return json.loads(raw_text)
    except Exception as e:
        print(f"[AGENT 1 ERROR] Communication or parsing failure: {e}")
        return {"goal": "", "steps": []}

def run_agent2_test_generator(validated_plan, test_knowledge, spec, implementation_context):
    """Run Agent 2 to generate a Parsl function for a validated workflow.
    Input:
        validated_plan (dict): Workflow plan accepted by the Python validator.
        test_knowledge (dict): Test knowledge base used to constrain the implementation.
        spec (dict): Implementation rules and framework requirements.
        implementation_context (str): Available Parsl app contracts extracted from apps.py.
    Output:
        str: Generated Python function implementing the validated tool sequence.
    """
    steps = validated_plan.get("steps", [])
    steps_str = " -> ".join(steps)
    workflow_name = validated_plan.get("workflow_name", "custom_workflow").lower().replace("-", "_")

    few_shot_example = '''
FEW-SHOT EXAMPLE OF EXPECTED OUTPUT:

def bucky_quartet_maxcut_snaq(bio_config, basedir, prepare_to_run):
    max_workers = bio_config.workflow_core * bio_config.workflow_node
    result = list()
    
    # Step 1: BUCKy
    ret_bucky = apps.bucky(basedir=basedir, config=bio_config, inputs=prepare_to_run)
    
    # Step 2: Quartet MaxCut
    ret_maxcut = apps.quartet_maxcut(basedir=basedir, config=bio_config, inputs=[ret_bucky])
    
    # Step 3: SNaQ
    pool_phylo = CircularList(math.floor(max_workers / int(bio_config.snaq_threads)))
    for h in bio_config.snaq_hmax:
        ret_snq = apps.snaq(basedir, config=bio_config, hmax=h, inputs=[ret_maxcut], next_pipe=pool_phylo.next())
        pool_phylo.current(ret_snq)
        result.append(ret_snq)
        
    return result
'''

    system_prompt = (
        "You are Agent 2: Test & Code Implementation Agent for HP2Net.\n"
        "Your task is ONLY to generate the single Python function for the requested steps.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. DO NOT output existing functions like raxml_snaq or iqtree_snaq.\n"
        "2. Implement ONLY the target steps chain.\n"
        "3. Output ONLY valid executable Python code without markdown blocks or text.\n\n"
        f"{few_shot_example}"
    )
    user_prompt = (
        f"TARGET STEPS: {steps_str}\n"
        f"FUNCTION NAME: {workflow_name}\n\n"
        f"SPECIFICATION RULES:\n{json.dumps(spec.get('rules', []), indent=2)}\n\n"
        f"AVAILABLE APPS CONTRACTS:\n{implementation_context}\n\n"
        f"Generate Python function {workflow_name}:"
    )
    payload = {
        "model": MODEL_NAME,
        "prompt": f"System: {system_prompt}\nUser: {user_prompt}",
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": 8192,
            "num_predict": 1024
        }
    }
    try:
        response = requests.post(OLLAMA_API_ENDPOINT, json=payload, timeout=300)
        response.raise_for_status()
        raw_content = response.json().get("response", "").strip()
        return extract_python_code(raw_content)
    except Exception as e:
        return f"# AGENT 2 ERROR: Failed to generate Python code: {e}"

def main():
    """Main CLI execution loop for orchestrating planning, validation, and code synthesis."""
    print("======================================================================")
    print("                PHYLO_AGENT 2 - HP2NET ORCHESTRATOR                   ")
    print("======================================================================\n")
    try:
        original_knowledge = read_json_file(ORIGINAL_KB_PATH)
        test_knowledge = read_json_file(TEST_KB_PATH)
    except Exception as e:
        print(f"[ERROR] Failed to load knowledge base files: {e}")
        return
    user_request = input("Enter workflow request: ").strip()
    if not user_request:
        user_request = "Use BUCKy to perform concordance analysis and then use SNaQ to infer a phylogenetic network."
        print(f"[INFO] Using default request: '{user_request}'\n")
    requested_tools = extract_requested_tools(user_request, original_knowledge)
    print(f"[0/3] Extracted requested tools: {requested_tools}")
    print("[1/3] Running Agent 1 (Planner over original HP2Net KB)...")
    agent1_output = run_agent1_planner(user_request, original_knowledge, requested_tools)
    proposed_steps = agent1_output.get("steps", [])
    proposed_steps = canonicalize_tool_names(proposed_steps, original_knowledge)
    goal = agent1_output.get("goal", user_request)
    print(f"      -> Goal: {goal}")
    print(f"      -> Proposed steps: {proposed_steps}\n")
    if not proposed_steps:
        print("[ERROR] Agent 1 did not generate a valid step sequence.")
        return
    valid_endpoints, endpoint_error = validate_endpoints(proposed_steps, requested_tools)
    if not valid_endpoints:
        print(f"[REJECTED BY PYTHON VALIDATOR] {endpoint_error}")
        print("[3/3] Agent 2 skipped.")
        return
    print("[2/3] Validating plan against Test KB...")
    validation = validate_composition(proposed_steps, test_knowledge)
    validated_plan = {
        "goal": goal,
        "workflow_name": "-".join(proposed_steps),
        "steps": proposed_steps,
        "status": validation.get("status"),
        "execution_status": validation.get("execution_status"),
        "implementation_notes": validation.get("implementation_notes")
    }
    print(f"      -> Validation status: {validated_plan['status']} ({validated_plan['execution_status']})")
    print(f"      -> Notes: {validated_plan['implementation_notes']}\n")
    status = validated_plan["status"]
    if status in ["existing_workflow", "existing_composition"]:
        print("[3/3] Agent 2 skipped.")
        print(f"      -> Workflow already exists and is implemented in the test KB: {validated_plan['implementation_notes']}")
        return
    if status != "new_supported_workflow":
        print("[3/3] Agent 2 skipped.")
        print("      -> Composition is not supported by the test KB.")
        return
    print("[3/3] Running Agent 2 (Parsl Code Generator)...")
    implementation_context = load_apps_context()
    generated_code = run_agent2_test_generator(
        validated_plan,
        test_knowledge,
        IMPLEMENTATION_SPEC,
        implementation_context
    )
    all_passed, checks, err_msg = validate_generated_code(generated_code, proposed_steps)
    print("Code Validation:")
    for check_name, check_status in checks.items():
        print(f"  {check_name}: {check_status}")
    print()
    if not all_passed:
        print(f"[ERROR] Code validation failed. Reason: {err_msg if err_msg else 'Semantic checks failed.'}")
        return
    print("======================================================================")
    print("CODE GENERATED BY AGENT 2:")
    print("======================================================================")
    print(generated_code)
    print("======================================================================")

if __name__ == "__main__":
    main()