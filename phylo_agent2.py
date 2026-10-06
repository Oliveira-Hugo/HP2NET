import json
import os
import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.1:8b"

HP2NET_KB_PATH = "knowledge/hp2net_knowledge.json"
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

def load_json_file(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def load_implementation_context():
    files = ["apps.py", "parsl_workflow.py", "bioconfig.py", "infra_manager.py", "utils.py"]
    context = []
    for filepath in files:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                context.append(f"\n===== {filepath} =====\n{f.read()}")
    if not context:
        return "No implementation files found locally. Use standard Parsl standard constructs if required."
    return "\n".join(context)

def validate_interfaces(steps, knowledge):
    interfaces = knowledge.get("interfaces", [])
    for i in range(len(steps) - 1):
        producer = steps[i]
        consumer = steps[i + 1]
        match = next((iface for iface in interfaces if iface.get("producer") == producer and iface.get("consumer") == consumer), None)
        if not match:
            return False, f"Nenhuma interface declarada entre {producer} e {consumer}."
        if not match.get("supported", False):
            return False, f"Interface entre {producer} e {consumer} declarada mas não suportada."
    return True, None

def validate_composition(steps, knowledge):
    requested_steps = list(steps)
    known_tools = set(knowledge.get("tools", {}).keys())
    unknown_tools = [tool for tool in requested_steps if tool not in known_tools]
    if unknown_tools:
        return {"status": "invalid_workflow", "execution_status": "unsupported", "implementation_notes": [f"Unknown tool(s): {', '.join(unknown_tools)}."]}
    
    valid_interfaces, interface_reason = validate_interfaces(requested_steps, knowledge)
    
    for workflow_name, workflow in knowledge.get("workflows", {}).items():
        if requested_steps == workflow.get("steps", []):
            implemented = workflow.get("implemented", False) and valid_interfaces
            notes = []
            if implemented:
                notes.append(f"Implemented as part of {workflow_name}.")
            if not valid_interfaces and interface_reason:
                notes.append(interface_reason)
            return {"status": "existing_workflow", "execution_status": "implemented" if implemented else "uncertain", "implementation_notes": notes}
            
    for composition in knowledge.get("supported_compositions", []):
        if requested_steps == composition.get("steps", []):
            implemented = composition.get("implemented", False) and valid_interfaces
            notes = []
            part_of = composition.get("implemented_as_part_of")
            if part_of:
                notes.append(f"Implemented as part of {part_of}.")
            if not valid_interfaces and interface_reason:
                notes.append(interface_reason)
            return {"status": "existing_composition", "execution_status": "implemented" if implemented else "uncertain", "implementation_notes": notes}
            
    if valid_interfaces:
        return {"status": "new_supported_workflow", "execution_status": "not_implemented", "implementation_notes": ["Valid and supported tool sequence in target KB."]}
    
    notes = [interface_reason] if interface_reason else []
    return {"status": "unsupported_composition", "execution_status": "unsupported", "implementation_notes": notes}

def run_agent1_planner(user_prompt, original_knowledge):
    system_prompt = (
        "You are an expert computational biology workflow planner for HP2Net.\n"
        "Translate the user's request into an ordered sequence of HP2Net tools.\n"
        "Use ONLY tools and workflow compositions defined in the original HP2Net knowledge base.\n"
        "Preserve the first and last tools explicitly requested by the user.\n"
        "If an implemented workflow or supported composition connects the requested endpoints, "
        "include all required intermediate tools from that workflow.\n"
        "Do not add tools before the first requested tool or after the last requested tool.\n"
        "Do not invent tools or intermediate steps.\n"
        f"Available original HP2Net knowledge:\n{json.dumps(original_knowledge, indent=2)}\n"
        "Output JSON with keys 'goal' (string) and 'steps' (list of strings)."
    )
    payload = {
        "model": MODEL_NAME,
        "prompt": f"System: {system_prompt}\nUser request: {user_prompt}",
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.0}
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        raw_text = response.json().get("response", "").strip()
        return json.loads(raw_text)
    except Exception as e:
        print(f"[ERRO AGENTE 1] Falha na comunicação ou parsing: {e}")
        return {"goal": "", "steps": []}

def run_agent2_test_generator(validated_plan, test_knowledge, spec, implementation_context):
    steps = validated_plan.get("steps", [])
    steps_str = " -> ".join(steps)
    workflow_name = validated_plan.get("workflow_name", "custom_workflow").lower().replace("-", "_")
    
    system_prompt = (
        "You are Agent 2: Test & Code Implementation Agent for HP2Net.\n"
        "The workflow has already been validated deterministically by Python.\n"
        "Your task is ONLY to implement the validated tool sequence using the target "
        "knowledge base and the supplied HP2Net implementation context.\n"
        "Do not replan, extend, reorder, or replace the validated steps.\n"
        "Output rules:\n"
        "- Output exactly one Python function starting with 'def'.\n"
        "- Do not return Markdown commentary or code blocks outside the pure code string."
    )
    user_prompt = (
        f"VALIDATED PLAN:\n{json.dumps(validated_plan, indent=2)}\n\n"
        f"TARGET TEST KNOWLEDGE BASE:\n{json.dumps(test_knowledge, indent=2)}\n\n"
        f"SPECIFICATION:\n{json.dumps(spec, indent=2)}\n\n"
        f"IMPLEMENTATION CONTEXT:\n{implementation_context}\n\n"
        f"Generate the Python function for workflow '{workflow_name}' ({steps_str}):"
    )
    payload = {
        "model": MODEL_NAME,
        "prompt": f"System: {system_prompt}\nUser: {user_prompt}",
        "stream": False,
        "options": {"temperature": 0.1}
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=90)
        response.raise_for_status()
        content = response.json().get("response", "").strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        return content
    except Exception as e:
        return f"# ERRO AGENTE 2: Falha ao gerar o código Python: {e}"

def main():
    print("======================================================================")
    print("                PHYLO_AGENT 2 - HP2NET ORCHESTRATOR                   ")
    print("======================================================================\n")
    try:
        original_knowledge = load_json_file(HP2NET_KB_PATH)
        test_knowledge = load_json_file(TEST_KB_PATH)
    except Exception as e:
        print(f"[ERRO] Falha ao carregar arquivos de conhecimento: {e}")
        return

    user_request = input("Digite a requisição de workflow: ").strip()
    if not user_request:
        user_request = "Use BUCKy to perform concordance analysis and then use SNaQ to infer a phylogenetic network."
        print(f"[INFO] Usando requisição padrão: '{user_request}'\n")

    print("[1/3] Executando Agente 1 (Planejador sobre HP2Net KB original)...")
    agent1_output = run_agent1_planner(user_request, original_knowledge)
    proposed_steps = agent1_output.get("steps", [])
    goal = agent1_output.get("goal", user_request)

    print(f"      -> Goal: {goal}")
    print(f"      -> Passos propostos: {proposed_steps}\n")

    if not proposed_steps:
        print("[ERRO] Agente 1 não gerou uma sequência de passos válida.")
        return

    print("[2/3] Validando plano contra a KB de Teste...")
    validation = validate_composition(proposed_steps, test_knowledge)
    validated_plan = {
        "goal": goal,
        "workflow_name": "-".join(proposed_steps),
        "steps": proposed_steps,
        "status": validation.get("status"),
        "execution_status": validation.get("execution_status"),
        "implementation_notes": validation.get("implementation_notes")
    }
    print(f"      -> Status da validação: {validated_plan['status']} ({validated_plan['execution_status']})")
    print(f"      -> Notas: {validated_plan['implementation_notes']}\n")

    status = validated_plan["status"]

    if status in ["existing_workflow", "existing_composition"]:
        print("[3/3] Agente 2 não executado.")
        print(f"      -> Workflow já existente e implementado na KB de teste: {validated_plan['implementation_notes']}")
        return

    if status != "new_supported_workflow":
        print("[3/3] Agente 2 não executado.")
        print("      -> A composição não é suportada pela KB de teste.")
        return

    print("[3/3] Executando Agente 2 (Gerador de Código Parsl)...")
    implementation_context = load_implementation_context()
    generated_code = run_agent2_test_generator(
        validated_plan,
        test_knowledge,
        IMPLEMENTATION_SPEC,
        implementation_context
    )

    print("======================================================================")
    print("CÓDIGO GERADO PELO AGENTE 2:")
    print("======================================================================")
    print(generated_code)
    print("======================================================================")

if __name__ == "__main__":
    main()