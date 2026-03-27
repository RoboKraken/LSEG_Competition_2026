import streamlit as st
import ollama
import json
import streamlit.components.v1 as components

# --- 1. GUI SETUP ---
st.set_page_config(page_title="AI Mermaid Diagrammer", layout="wide")
st.title("AI Diagram Generator")
st.caption("Generate structured Mermaid.js diagrams from natural language descriptions using DeepSeek-R1.")

# User Input
with st.sidebar:
    st.header("Configuration")
    model_name = st.text_input("Ollama Model", value="deepseek-r1:7b")
    st.info("Ensure the model is pulled: `ollama pull deepseek-r1:7b`")

user_prompt = st.text_area(
    "Describe your process, system, or flow:",
    placeholder="Example: A user logs in. If successful, show dashboard. If it fails, show error and return to login.",
    height=150
)

col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    run_btn = st.button("Generate Diagram", type="primary")
with col_btn2:
    check_btn = st.button("Check")

# --- 2. HELPERS ---

def render_mermaid(code):
    """Renders Mermaid code using a CDN-loaded script in an iframe."""
    components.html(
        f"""
        <div class="mermaid" style="display: flex; justify-content: center;">
            {code}
        </div>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
        </script>
        """,
        height=500,
        scrolling=True
    )

def get_diagram_structure(prompt, model):
    """Calls Ollama to get a structured JSON representation of the diagram."""
    system_msg = (
        "You are a diagram architect. Analyze the user's natural language description "
        "and infer a logical diagram structure. Output ONLY valid JSON.\n"
        "The JSON must follow this structure:\n"
        "{\n"
        "  'type': 'graph TD' or 'graph LR',\n"
        "  'nodes': [{'id': 'unique_id', 'label': 'display_text'}],\n"
        "  'edges': [{'from': 'source_id', 'to': 'target_id', 'label': 'optional_text'}]\n"
        "}"
    )
    
    full_prompt = f"System: {system_msg}\nUser Description: {prompt}"
    
    # Using format='json' to ensure structured output
    response = ollama.generate(
        model=model,
        prompt=full_prompt,
        format='json'
    )
    
    return json.loads(response['response'])

def check_diagram_structure(prompt, current_structure, current_mermaid, model):
    """Calls Ollama to verify and refine the diagram structure against the current prompt."""
    system_msg = (
        "You are a quality assurance architect. Your task is to verify if the current Mermaid diagram "
        "and its JSON structure perfectly match the LATEST user description. If the description has changed "
        "or if there are errors, missing steps, or logical inconsistencies, provide a corrected and "
        "optimized version. Be thorough. Output ONLY valid JSON.\n"
        "The JSON must follow this structure:\n"
        "{\n"
        "  'type': 'graph TD' or 'graph LR',\n"
        "  'nodes': [{'id': 'unique_id', 'label': 'display_text'}],\n"
        "  'edges': [{'from': 'source_id', 'to': 'target_id', 'label': 'optional_text'}]\n"
        "}"
    )
    
    full_prompt = (
        f"System: {system_msg}\n"
        f"LATEST User Description: {prompt}\n"
        f"Current Mermaid Code:\n{current_mermaid}\n"
        f"Current JSON Structure: {json.dumps(current_structure)}\n"
        f"Please compare the structure against the LATEST description and provide the final improved JSON structure."
    )
    
    response = ollama.generate(
        model=model,
        prompt=full_prompt,
        format='json'
    )
    
    return json.loads(response['response'])

def convert_to_mermaid(data):
    """Converts the structured JSON into Mermaid.js syntax."""
    # Using 'flowchart' instead of 'graph' for better v10+ compatibility
    diag_type = data.get('type', 'flowchart TD').replace('graph', 'flowchart')
    lines = [diag_type]
    
    def safe_id(id_val):
        # Mermaid IDs cannot start with a number or contain special chars easily
        id_str = str(id_val) if id_val is not None else "unknown"
        if id_str and id_str[0].isdigit():
            return f"n{id_str}"
        return id_str

    # Define Nodes
    for node in data.get('nodes', []):
        nid = safe_id(node.get('id', 'unknown'))
        label = node.get('label', '')
        label_text = f"\"{label}\"" if label else f"\"{nid}\""
        lines.append(f"    {nid}[{label_text}]")
    
    # Define Edges
    for edge in data.get('edges', []):
        # Using .get() to prevent KeyError if model returns 'source'/'target' or missing keys
        source = safe_id(edge.get('from', edge.get('source', '')))
        target = safe_id(edge.get('to', edge.get('target', '')))
        if not source or not target:
            continue
            
        label = f"|{edge['label']}| " if edge.get('label') else ""
        lines.append(f"    {source} --> {label}{target}")
        
    return "\n".join(lines)

# --- 3. EXECUTION ---

# Initialize session state
if 'structured_data' not in st.session_state:
    st.session_state.structured_data = None
if 'mermaid_code' not in st.session_state:
    st.session_state.mermaid_code = None

if run_btn:
    if not user_prompt:
        st.warning("Please enter a description first.")
    else:
        with st.spinner("DeepSeek is analyzing the logic and structuring the diagram..."):
            try:
                # Step 1: Get JSON from AI
                st.session_state.structured_data = get_diagram_structure(user_prompt, model_name)
                # Step 2: Convert to Mermaid syntax
                st.session_state.mermaid_code = convert_to_mermaid(st.session_state.structured_data)
                st.rerun() # Ensure UI refreshes with new data
            except Exception as e:
                st.error(f"An error occurred during generation: {str(e)}")

if check_btn:
    if not user_prompt:
        st.warning("Please enter a description first.")
    elif not st.session_state.structured_data:
        st.warning("Please generate a diagram first before checking.")
    else:
        with st.spinner("DeepSeek is verifying and refining the diagram..."):
            try:
                # Step 1: Check/Refine JSON from AI
                new_data = check_diagram_structure(
                    user_prompt, 
                    st.session_state.structured_data, 
                    st.session_state.mermaid_code,
                    model_name
                )
                
                # Check if data actually changed to provide feedback
                if new_data != st.session_state.structured_data:
                    st.session_state.structured_data = new_data
                    st.session_state.mermaid_code = convert_to_mermaid(st.session_state.structured_data)
                    st.success("Diagram updated based on the current prompt!")
                else:
                    st.info("The current diagram already matches the prompt perfectly.")
                    
            except Exception as e:
                st.error(f"An error occurred during verification: {str(e)}")

# Display Results if they exist in session state
if st.session_state.structured_data and st.session_state.mermaid_code:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Inferred Structure")
        st.json(st.session_state.structured_data)
        
        st.subheader("Mermaid Syntax")
        st.code(st.session_state.mermaid_code, language="mermaid")
    
    with col2:
        st.subheader("Visual Diagram")
        # Show the rendered diagram
        render_mermaid(st.session_state.mermaid_code)

# --- 4. INSTRUCTIONS ---
if not st.session_state.structured_data:
    st.write("---")
    st.markdown("""
    ### How it works:
    1. **Natural Language Input**: You describe a flow or system in plain English.
    2. **DeepSeek-R1 Inference**: The model decides what the nodes and connections are.
    3. **Structured JSON**: We extract a clean `nodes` and `edges` list.
    4. **Mermaid.js**: The JSON is mapped to Mermaid syntax and rendered live.
    """)
