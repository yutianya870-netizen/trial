import streamlit.components.v1 as components
import os

print("—__init__.py被导入，正在声明组件...")
_component_func = components.declare_component(
    "pdf_graph_component",
    path=os.path.join(os.path.dirname(__file__), "frontend/build")
)

def note_component(base64_pdf=None, component="pdf", key=None):
    print("note_component被调用")
    return _component_func(base64_pdf=base64_pdf, component=component, key=key)

def graph_component(graph=None, component="graph", key=None):
    print("graph_component被调用")
    return _component_func(graph=graph, component=component, key=key)