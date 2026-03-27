import streamlit as st
import ollama
import json
import streamlit.components.v1 as components
import pandas as pd

# --- 1. CONSTANTS & CONFIG ---
SHAPE_MAP = {
    "default": ("[", "]"),
    "rounded": ("(", ")"),
    "stadium": ("([", "])"),
    "subroutine": ("[[", "]]"),
    "database": ("[(", ")]"),
    "circle": ("((", "))"),
    "rhombus": ("{", "}"),
    "hexagon": ("{{", "}}"),
    "parallelogram": ("[/", "/]"),
}

# --- 2. GUI SETUP ---
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

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])
with col_btn1:
    run_btn = st.button("Generate", type="primary", use_container_width=True)
with col_btn2:
    check_btn = st.button("Check", use_container_width=True)
with col_btn3:
    style_btn = st.button("Generate Aesthetics", use_container_width=False)

# --- 3. HELPERS ---

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
    """Calls Ollama to get a structured JSON representation of the diagram structure only."""
    system_msg = (
        "You are a technical architect. Analyze the user's natural language description "
        "and infer a logical diagram structure. Ignore aesthetics (colors/shapes of nodes), DO NOT PUT color or shapes IN LABELS. \n"
        "Output ONLY valid JSON.\n"
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
    """Refines the diagram structure. Preserves existing aesthetic fields if present."""
    system_msg = (
        "You are a quality assurance architect. Verify if the current diagram matches the LATEST description. "
        "Focus on logic and structure. If 'shape' or 'color' fields exist in the nodes, PRESERVE THEM. Otherwise do not \n"
        "Output ONLY valid JSON.\n"
        "The JSON must follow this structure:\n"
        "{\n"
        "  'type': 'graph TD' or 'graph LR',\n"
        "  'nodes': [{'id': 'unique_id', 'label': 'display_text', 'shape': '...', 'color': '...'}],\n"
        "  'edges': [{'from': 'source_id', 'to': 'target_id', 'label': 'optional_text'}]\n"
        "}"
    )
    
    full_prompt = (
        f"System: {system_msg}\n"
        f"LATEST User Description: {prompt}\n"
        f"Current JSON Structure: {json.dumps(current_structure)}\n"
        f"Please provide the final improved JSON structure, preserving any existing 'shape' or 'color' fields."
    )
    
    response = ollama.generate(
        model=model,
        prompt=full_prompt,
        format='json'
    )
    
    return json.loads(response['response'])

def get_diagram_aesthetics(prompt, current_structure, model):
    """Infers shapes and colors for existing nodes based on semantic meaning.
    This version extracts nodes, gets styles from AI, and merges them back 
    to ensure the structure (edges/ids) is never modified.
    """
    # Extract only necessary info to keep the LLM focused
    nodes_to_style = [{"id": n["id"], "label": n["label"]} for n in current_structure.get('nodes', [])]

    system_msg = (
        "You are a visual designer. Your ONLY task is to assign a 'shape' and 'color' to the provided nodes.\n"
        "Rules:\n"
        f"1. Choose 'shape' from: {list(SHAPE_MAP.keys())}.\n"
        "   - Use 'rhombus' for decisions, 'database' for storage, 'stadium' for start/end.\n"
        "2. Choose 'color' as a HEX code (e.g., #f9f).\n"
        "3. DO NOT change 'id' or 'label'. DO NOT add or remove nodes.\n"
        "Output ONLY valid JSON: {'nodes': [{'id': '...', 'shape': '...', 'color': '...'}]}"
    )
    
    full_prompt = (
        f"System: {system_msg}\n"
        f"Original Description: {prompt}\n"
        f"Nodes to Style: {json.dumps(nodes_to_style)}"
    )
    
    response = ollama.generate(
        model=model,
        prompt=full_prompt,
        format='json'
    )
    
    try:
        res_data = json.loads(response['response'])
        styled_list = res_data.get('nodes', []) if isinstance(res_data, dict) else res_data
        
        # Create a lookup map for the styles
        style_lookup = {str(n.get('id')): n for n in styled_list if n.get('id')}
        
        # Merge styles back into the original structure (Non-destructive)
        for node in current_structure.get('nodes', []):
            style_info = style_lookup.get(str(node.get('id')))
            if style_info:
                node['shape'] = style_info.get('shape', node.get('shape', 'default'))
                node['color'] = style_info.get('color', node.get('color', ''))
                
        return current_structure
    except Exception as e:
        st.error(f"Failed to parse aesthetics: {e}")
        return current_structure

def convert_to_mermaid(data, orientation_override=None):
    """Converts the structured JSON into Mermaid.js syntax with styling support."""
    raw_type = data.get('type', 'flowchart TD')
    diag_type = f"flowchart {orientation_override}" if orientation_override else raw_type.replace('graph', 'flowchart')
        
    lines = [diag_type]
    styles = []
    
    def safe_id(id_val):
        id_str = str(id_val) if id_val is not None else "unknown"
        return f"n{id_str}" if id_str and id_str[0].isdigit() else id_str

    # Define Nodes
    for node in data.get('nodes', []):
        nid = safe_id(node.get('id', 'unknown'))
        label = node.get('label', nid)
        shape_type = node.get('shape', 'default')
        open_b, close_b = SHAPE_MAP.get(shape_type, SHAPE_MAP['default'])
        
        lines.append(f"    {nid}{open_b}\"{label}\"{close_b}")
        
        # Add Style
        color = node.get('color')
        if color:
            # Ensure color has # if it's a hex
            color_str = str(color)
            if color_str.startswith('#') or len(color_str) in [3, 6]:
                color_val = color_str if color_str.startswith('#') else f"#{color_str}"
                styles.append(f"    style {nid} fill:{color_val}")

    # Define Edges
    for edge in data.get('edges', []):
        source = safe_id(edge.get('from', edge.get('source', '')))
        target = safe_id(edge.get('to', edge.get('target', '')))
        if not source or not target: continue
            
        label = f"|{edge.get('label', '')}| " if edge.get('label') else ""
        lines.append(f"    {source} --> {label}{target}")
        
    return "\n".join(lines + styles)

# --- 4. EXECUTION ---

if 'structured_data' not in st.session_state:
    st.session_state.structured_data = None
if 'mermaid_code' not in st.session_state:
    st.session_state.mermaid_code = None

if run_btn:
    if not user_prompt:
        st.warning("Please enter a description first.")
    else:
        with st.spinner("Analyzing logic..."):
            try:
                st.session_state.structured_data = get_diagram_structure(user_prompt, model_name)
                st.session_state.mermaid_code = convert_to_mermaid(st.session_state.structured_data)
                st.rerun()
            except Exception as e:
                st.error(f"Generation error: {str(e)}")

if check_btn:
    if not st.session_state.structured_data:
        st.warning("Generate a diagram first.")
    else:
        with st.spinner("Verifying structure..."):
            try:
                st.session_state.structured_data = check_diagram_structure(
                    user_prompt, st.session_state.structured_data, st.session_state.mermaid_code, model_name
                )
                st.session_state.mermaid_code = convert_to_mermaid(st.session_state.structured_data)
                st.success("Structure updated!")
            except Exception as e:
                st.error(f"Verification error: {str(e)}")

if style_btn:
    if not st.session_state.structured_data:
        st.warning("Generate a diagram first.")
    else:
        with st.spinner("Inferring aesthetics..."):
            try:
                st.session_state.structured_data = get_diagram_aesthetics(
                    user_prompt, st.session_state.structured_data, model_name
                )
                st.session_state.mermaid_code = convert_to_mermaid(st.session_state.structured_data)
                st.success("Aesthetics applied!")
            except Exception as e:
                st.error(f"Aesthetics error: {str(e)}")

# Display Results
if st.session_state.structured_data:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Interactive Editor")
        current_orientation = diag_orientation.split(" ")[0]
        
        # Nodes Editor
        st.write("**Nodes**")
        nodes_df = pd.DataFrame(st.session_state.structured_data.get('nodes', []))
        for col in ['id', 'label', 'shape', 'color']:
            if col not in nodes_df.columns: nodes_df[col] = ""
        
        edited_nodes = st.data_editor(
            nodes_df, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "shape": st.column_config.SelectboxColumn("Shape", options=list(SHAPE_MAP.keys())),
                "color": st.column_config.TextColumn("Color (Hex)")
            },
            key="node_editor"
        )
        
        # Edges Editor
        st.write("**Edges (Connections)**")
        edges_df = pd.DataFrame(st.session_state.structured_data.get('edges', []))
        for col in ['from', 'to', 'label']:
            if col not in edges_df.columns: edges_df[col] = ""

        edited_edges = st.data_editor(edges_df, num_rows="dynamic", use_container_width=True, key="edge_editor")
        
        # Sync logic
        new_nodes = edited_nodes.to_dict('records')
        new_edges = edited_edges.to_dict('records')
        
        if (new_nodes != st.session_state.structured_data.get('nodes') or 
            new_edges != st.session_state.structured_data.get('edges') or
            st.session_state.get('last_orientation') != current_orientation):
            
            st.session_state.structured_data.update({'nodes': new_nodes, 'edges': new_edges, 'type': f"flowchart {current_orientation}"})
            st.session_state.mermaid_code = convert_to_mermaid(st.session_state.structured_data, current_orientation)
            st.session_state['last_orientation'] = current_orientation

        with st.expander("Raw Data"):
            st.json(st.session_state.structured_data)
            st.code(st.session_state.mermaid_code, language="mermaid")
    
    with col2:
        st.subheader("Visual Diagram")
        render_mermaid(st.session_state.mermaid_code)
