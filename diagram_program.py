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

run_btn = st.button("Generate Diagram", type="primary")

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
    
    # Using format='json' to ensure structured output
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
        # We prefix with 'n' if it starts with a digit
        id_str = str(id_val)
        if id_str and id_str[0].isdigit():
            return f"n{id_str}"
        return id_str

    # Define Nodes
    for node in data.get('nodes', []):
        nid = safe_id(node['id'])
        label = node.get('label', '')
        # If label is empty, use the ID or a space to avoid syntax errors
        label_text = f"\"{label}\"" if label else f"\"{nid}\""
        lines.append(f"    {nid}[{label_text}]")
    
    # Define Edges
    for edge in data.get('edges', []):
        source = safe_id(edge['from'])
        target = safe_id(edge['to'])
        label = f"|{edge['label']}| " if edge.get('label') else ""
        lines.append(f"    {source} --> {label}{target}")
        
    return "\n".join(lines)

# --- 3. EXECUTION ---

if run_btn:
    if not user_prompt:
        st.warning("Please enter a description first.")
    else:
        with st.spinner("DeepSeek is analyzing the logic and structuring the diagram..."):
            try:
                # Step 1: Get JSON from AI
                structured_data = get_diagram_structure(user_prompt, model_name)
                
                # Step 2: Convert to Mermaid syntax
                mermaid_code = convert_to_mermaid(structured_data)
                
                # Step 3: Display Results
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.subheader("Inferred Structure")
                    st.json(structured_data)
                    
                    st.subheader("Mermaid Syntax")
                    st.code(mermaid_code, language="mermaid")
                
                with col2:
                    st.subheader("Visual Diagram")
                    # Show the rendered diagram
                    render_mermaid(mermaid_code)
                    
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.info("Sometimes the model might return malformed JSON. Try clicking Generate again.")

# --- 4. INSTRUCTIONS ---
else:
    st.write("---")
    st.markdown("""
    ### How it works:
    1. **Natural Language Input**: You describe a flow or system in plain English.
    2. **DeepSeek-R1 Inference**: The model decides what the nodes and connections are.
    3. **Structured JSON**: We extract a clean `nodes` and `edges` list.
    4. **Mermaid.js**: The JSON is mapped to Mermaid syntax and rendered live.
    """)
