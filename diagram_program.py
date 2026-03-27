import streamlit as st
import ollama
import json
import streamlit.components.v1 as components
import pandas as pd

# --- 1. GUI SETUP ---
st.set_page_config(page_title="AI Mermaid Diagrammer", layout="wide")
st.title("AI Diagram Generator")
st.caption("Generate and interactively edit Mermaid.js diagrams from natural language descriptions.")

# User Input
with st.sidebar:
    st.header("Configuration")
    model_name = st.text_input("Ollama Model", value="deepseek-r1:7b")
    st.info("Ensure the model is pulled: `ollama pull deepseek-r1:7b`")
    
    st.divider()
    st.subheader("Global Settings")
    diag_orientation = st.radio("Diagram Orientation", ["TD (Top-Down)", "LR (Left-Right)"], index=0)

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
        height=600,
        scrolling=True
    )

def get_diagram_structure(prompt, model):
    """Calls Ollama to get a structured JSON representation of the diagram."""
    system_msg = (
        "You are a technical architect. Analyze the user's natural language description "
        "and infer a logical diagram structure. Output ONLY valid JSON.\n"
        "The JSON must follow this structure:\n"
        "{\n"
        "  'type': 'graph TD' or 'graph LR',\n"
        "  'nodes': [{'id': 'unique_id', 'label': 'display_text'}],\n"
        "  'edges': [{'from': 'source_id', 'to': 'target_id', 'label': 'optional_text'}]\n"
        "}"
    )
    
    full_prompt = f"System: {system_msg}\nUser Description: {prompt}"
    
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

def convert_to_mermaid(data, orientation_override=None):
    """Converts the structured JSON into Mermaid.js syntax."""
    # Priority: Override -> JSON Data -> Default TD
    raw_type = data.get('type', 'flowchart TD')
    if orientation_override:
        diag_type = f"flowchart {orientation_override}"
    else:
        diag_type = raw_type.replace('graph', 'flowchart')
        
    lines = [diag_type]
    
    def safe_id(id_val):
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
        source = safe_id(edge.get('from', edge.get('source', '')))
        target = safe_id(edge.get('to', edge.get('target', '')))
        if not source or not target:
            continue
            
        label = f"|{edge.get('label', '')}| " if edge.get('label') else ""
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
                st.session_state.structured_data = get_diagram_structure(user_prompt, model_name)
                st.session_state.mermaid_code = convert_to_mermaid(st.session_state.structured_data)
                st.rerun()
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
                new_data = check_diagram_structure(
                    user_prompt, 
                    st.session_state.structured_data, 
                    st.session_state.mermaid_code,
                    model_name
                )
                if new_data != st.session_state.structured_data:
                    st.session_state.structured_data = new_data
                    st.session_state.mermaid_code = convert_to_mermaid(st.session_state.structured_data)
                    st.success("Diagram updated!")
                else:
                    st.info("The diagram is already optimized.")
            except Exception as e:
                st.error(f"An error occurred during verification: {str(e)}")

# Display Results if they exist in session state
if st.session_state.structured_data:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Interactive Editor")
        
        # Orientaton from sidebar
        current_orientation = diag_orientation.split(" ")[0]
        
        # Nodes Editor
        st.write("**Nodes**")
        nodes_df = pd.DataFrame(st.session_state.structured_data.get('nodes', []))
        if nodes_df.empty:
            nodes_df = pd.DataFrame(columns=['id', 'label'])
        
        edited_nodes = st.data_editor(
            nodes_df, 
            num_rows="dynamic", 
            use_container_width=True,
            key="node_editor"
        )
        
        # Edges Editor
        st.write("**Edges (Connections)**")
        edges_df = pd.DataFrame(st.session_state.structured_data.get('edges', []))
        if edges_df.empty:
            edges_df = pd.DataFrame(columns=['from', 'to', 'label'])
        
        # Ensure we don't crash if 'from'/'to' are missing in some rows
        for col in ['from', 'to', 'label']:
            if col not in edges_df.columns:
                edges_df[col] = ""

        edited_edges = st.data_editor(
            edges_df, 
            num_rows="dynamic", 
            use_container_width=True,
            key="edge_editor"
        )
        
        # Update Master State if edited
        new_nodes = edited_nodes.to_dict('records')
        new_edges = edited_edges.to_dict('records')
        
        if (new_nodes != st.session_state.structured_data.get('nodes') or 
            new_edges != st.session_state.structured_data.get('edges') or
            st.session_state.get('last_orientation') != current_orientation):
            
            st.session_state.structured_data['nodes'] = new_nodes
            st.session_state.structured_data['edges'] = new_edges
            st.session_state.structured_data['type'] = f"flowchart {current_orientation}"
            st.session_state.mermaid_code = convert_to_mermaid(st.session_state.structured_data, current_orientation)
            st.session_state['last_orientation'] = current_orientation

        # Collapsed Raw Views
        with st.expander("View Inferred JSON Structure"):
            st.json(st.session_state.structured_data)
        
        with st.expander("View Mermaid Syntax"):
            st.code(st.session_state.mermaid_code, language="mermaid")
    
    with col2:
        st.subheader("Visual Diagram")
        render_mermaid(st.session_state.mermaid_code)

# --- 4. INSTRUCTIONS ---
if not st.session_state.structured_data:
    st.write("---")
    st.markdown("""
    ### How it works:
    1. **Natural Language Input**: Describe a flow or system in plain English.
    2. **DeepSeek-R1 Inference**: The AI structures the logic into nodes and edges.
    3. **Interactive Editing**: Manually refine the diagram using the tables on the left.
    4. **Automatic Rendering**: Changes sync instantly to the visual graph.
    """)
