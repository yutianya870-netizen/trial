# =========================文件注释============================
# 已实现的功能：思维导图和AI问答功能可切换，上传文献后用户可以在pdf文献中划线做笔记，系统自动更新思维导图形成用户的知识图示，同时用户也可以自主编辑节点之间的连线从而将零散的划线重点有序组织起来；AI问答可以为用户在学术阅读过程中答疑解惑，它会结合用户笔记和思维导图内容进行回答，帮助用户有效激发已有知识图示并鼓励优化跨模块之间的联系

import streamlit as st
import base64
from openai import OpenAI
import re
import streamlit.components.v1 as components
import json
from my_component import note_component, graph_component

#初始化API客户端
client = OpenAI(api_key="sk-cfa6a53f3cc749aa9eea158c0855f477",base_url="https://api.deepseek.com/v1")

#生成思维导图的reactflow代码
def generate_mind_map(user_text,current_graph="",text_category=""):
    prompt = f"""
    你是一名教育技术学领域的顶端专家，擅长知识结构建构，理解认知过程的同化和顺应原则。
    请根据提供的【参考文本】在【现有图结构】上进行“增量更新”，生成 React Flow 格式的图数据。

    【参考文本】：
    {user_text}

    【现有结构】（如果是空的则忽略）：
    {json.dumps(current_graph, ensure_ascii=False)}
    
    【分类规则（最高优先级）】
    用户选择分类{text_category}若不是“自动识别”，只能在该模块内寻找可同化节点或创建新分支；若是“自动识别”，先判断模块，再进行同化

    【结构原则（次高优先级）】：
    1.同化优先（最重要，必须遵循）：优先判断“新内容是否可以挂到已有节点下”，如果新知识点与已有节点语义相关（概念一致/上下位关系/解释关系），则将新知识点作为现有节点的子节点添加。
    2.顺应次之，如果找不到合适的已有节点，才允许在相应模块下创建新分支

    【结构深度强制要求（必须遵守）】
    1.每次新增内容必须生成2级及以上层级
    2.严禁只生成一个节点，必须生成至少一个父子关系
    3.每个节点只能表达“一个单一概念”，禁止合并多个含义

    【信息拆解规则】
    对于输入文本，必须执行以下拆解：
    1. 关键概念（名词）→ 节点
    2. 属性/作用/结果 → 子节点
    3. 因果关系 → 拆成父子结构

    示例：
    输入：认知提示提升学习成绩和问题解决能力
    必须拆为：
    - 认知提示
    - 提升学习成绩
    - 提升问题解决能力

    【结构层级要求】
    1.顶层节点：VR学习中的提示策略（id: root, 不可以改变）
    2.二级节点：研究背景(id: background)、研究问题(id: question)、研究方法(id: method)、研究结论(id: conclusion)（必须包含且不可以改变）
    3.三级节点及以下节点：根据概念和输入内容树状递进

    【节点生成规则】
    1.每个节点必须包含：
    {{
        "id": "唯一字符串",
        "data": {{"label": "节点名称"}},  
    }}
    2.生成的节点概念必须严格源自【参考文本】，严禁自行引入文本中不存在的学术术语或第三方概念；节点文本控制在15字以内，使用专业学术术语

    【边规则】
    每条边必须符合以下格式要求：
    {{
        "id": "e-source-target",
        "source": "节点id",
        "target": "节点id",
        "label": "关系（可选）"
    }}

    【连接规则】
    1.优先“树状结构”（父子关系），禁止滥用跨模块（如研究背景下的三级节点连接研究方法下的节点）连接边
    
    【输出要求】
    只输出JSON，禁止解释：
    {{
    "nodes": [...],
    "edges": [...]
    }} 

    请开始生成：
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": prompt},
                    {"role": "user", "content": user_text}],
            temperature=0.3
        )
        content=response.choices[0].message.content
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            graph_data = json.loads(json_match.group())
            if "nodes" in graph_data and "edges" in graph_data:
                return graph_data
            else:
                st.error("JSON结构错误")
                return current_graph
        else:
            st.error("AI response does not contain valid JSON.")
            return current_graph
    except Exception as e:
        st.error(f"API fails to generate proper text: {e}")
        return current_graph

#将思维导图的内容转化为大模型能理解的自然语言
def format_graph_for_llm(graph):
    node_map = {node["id"]: node["data"]["label"] for node in graph["nodes"]}
    relations = []
    # 结构边
    for edge in graph["edges"]:
        source_label = node_map.get(edge["source"], "Unknown")
        target_label = node_map.get(edge["target"], "Unknown")
        relations.append(f"{source_label} => {target_label}")
    # 用户边
    for edge in graph.get("user_edges", []):
        source_label = node_map.get(edge["source"], "Unknown")
        target_label = node_map.get(edge["target"], "Unknown")
        relation = edge.get("label", "related to")
        relations.append(f"{source_label} -[{relation}]-> {target_label}")
    return "\n".join(relations)

#定义笔记存储结构
if "notes" not in st.session_state:
    st.session_state.notes = {
        "研究背景": [],
        "研究问题": [],
        "研究方法": [],
        "研究结论": [],
        "自动识别": []
    }

# 定义chat历史记录
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "task_queue" not in st.session_state:
    st.session_state.task_queue = []
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

if "status_msg" not in st.session_state:
    st.session_state.status_msg = ""
if "status_type" not in st.session_state:
    st.session_state.status_type = "info"

# 右半侧页面切换
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "mind_map"  # 默认显示思维导图

# Streamlit 整体界面逻辑
st.set_page_config(page_title="AI Reading Demo", layout="wide")


# st.title("AI Reading Demo")
st.markdown("""
<style>
.block-container{padding-top: 3rem;}
.main{padding-top: 0rem;}
</style>
""", unsafe_allow_html=True)

#使用Session State来存储当前的React Flow graph数据
if "current_graph" not in st.session_state:
    st.session_state.current_graph = {
        "nodes": [
            {"id": "R", "data": {"label": "VR学习中的提示策略"}},
            {"id": "B", "data": {"label": "研究背景"}},
            {"id": "Q", "data": {"label": "研究问题"}},
            {"id": "M", "data": {"label": "研究方法"}},
            {"id": "C", "data": {"label": "研究结论"}},

            # ===== 背景子节点 =====
            {"id": "B1", "data": {"label": "VR学习的优势与问题"}},
            {"id": "B2", "data": {"label": "提示策略的重要性"}},
            {"id": "B3", "data": {"label": "游戏化学习提升动机"}},

            # ===== 问题子节点 =====
            {"id": "Q1", "data": {"label": "不同提示策略对学习成绩的影响"}},
            {"id": "Q2", "data": {"label": "不同提示策略对问题解决的影响"}},
            {"id": "Q3", "data": {"label": "不同提示策略对自我效能的影响"}},

            # ===== 方法子节点 =====
            {"id": "M1", "data": {"label": "构建VR学习系统"}},
            {"id": "M2", "data": {"label": "四组实验设计"}},
            {"id": "M3", "data": {"label": "ANCOVA分析"}},

            # ===== 结论子节点 =====
            {"id": "C1", "data": {"label": "认知提示提升成绩"}},
            {"id": "C2", "data": {"label": "认知提示提升问题解决能力"}},
            {"id": "C3", "data": {"label": "认知提示比混合提示更有效解决问题"}},
            {"id": "C4", "data": {"label": "认知提示提升自我效能"}},
        ],

        "edges":[
            {"id": "eR-B", "source": "R", "target": "B"},
            {"id": "eR-Q", "source": "R", "target": "Q"},
            {"id": "eR-M", "source": "R", "target": "M"},
            {"id": "eR-C", "source": "R", "target": "C"},

            {"id": "eB-B1", "source": "B", "target": "B1"},
            {"id": "eB-B2", "source": "B", "target": "B2"},
            {"id": "eB-B3", "source": "B", "target": "B3"},

            {"id": "eQ-Q1", "source": "Q", "target": "Q1"},
            {"id": "eQ-Q2", "source": "Q", "target": "Q2"},
            {"id": "eQ-Q3", "source": "Q", "target": "Q3"},

            {"id": "eM-M1", "source": "M", "target": "M1"},
            {"id": "eM-M2", "source": "M", "target": "M2"},
            {"id": "eM-M3", "source": "M", "target": "M3"},

            {"id": "eC-C1", "source": "C", "target": "C1"},
            {"id": "eC-C2", "source": "C", "target": "C2"},
            {"id": "eC-C3", "source": "C", "target": "C3"},
            {"id": "eC-C4", "source": "C", "target": "C4"},
        ],
        
        "user_edges": []
    }

#页面布局
col1, col2 = st.columns(2)
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
    
with col1:
    if st.session_state.uploaded_file is None:
        upload = st.file_uploader(label="", type="pdf",label_visibility="collapsed")
        st.markdown("""
                <div style="
                    height: 680px;
                    border: 2px dashed #ccc;
                    border-radius: 10px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #999;
                    font-size: 18px;
                ">
                    Upload your literature.
                </div>
                """, unsafe_allow_html=True)

        if upload is not None:
            st.session_state.uploaded_file = upload
            st.rerun()  # Refresh the page to show the uploaded file content
    else:
        uploaded_file = st.session_state.uploaded_file
        # st.write("是否有文件：", uploaded_file is not None)
        #st.success("File uploaded successfully!")
        col_btn1, col_btn2 = st.columns([8,2])
        with col_btn2:
            if st.button("Change File"):
                st.session_state.uploaded_file = None
                st.session_state.pop("pdf_base64", None)  # Clear the cached base64 PDF when changing file

        # Read the PDF file
        if "pdf_base64" not in st.session_state:
            pdf_bytes = uploaded_file.read()
            st.session_state.pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        note_data = note_component(base64_pdf=st.session_state.pdf_base64, component="pdf", key="pdf_viewer")  # 从自定义组件获取笔记数据,固定key，依赖组件内部逻辑判断是否需要更新显示内容,key 不变 → React 不会被销毁重建

        if note_data:
            # st.write(f"Received note data: {note_data}")  # Debug输出接收到的数据
            user_input = note_data["text"]
            text_category = note_data["category"]
            if st.session_state.get("last_note") != user_input:  # 避免重复处理同一笔记
                st.session_state.task_queue.append({
                    "type": "graph",
                    "text": user_input,
                    "category": text_category
                })

                st.session_state.last_note = user_input
                st.session_state.notes[text_category].append(user_input)
                # with st.spinner("Grasping meaning and Generating mind map..."):
                #     new_graph = generate_mind_map(
                #         user_input,
                #         {
                #             "nodes": st.session_state.current_graph["nodes"],
                #             "edges": st.session_state.current_graph["edges"]
                #         },
                #         text_category)
                #     if new_graph:
                #         st.session_state.current_graph["nodes"] = new_graph["nodes"]
                #         st.session_state.current_graph["edges"] = new_graph["edges"]
                #         st.success("Mind map generated successfully!")
        
with col2:
    top_col1,top_col2 = st.columns([2,3])
    with top_col1:
        st.session_state.view_mode = st.radio("Select View", ("mind_map", "chat"), horizontal=True, label_visibility="collapsed")
    with top_col2:
        status_placeholder = st.empty()

    if st.session_state.status_msg:
        if st.session_state.status_type == "info":
            status_placeholder.info(st.session_state.status_msg)
        elif st.session_state.status_type == "success":
            status_placeholder.success(st.session_state.status_msg)
        elif st.session_state.status_type == "warning":
            status_placeholder.warning(st.session_state.status_msg)
    
    if st.session_state.view_mode == "mind_map":
        # st.header("Mind Map")
        # st.write("准备调用graph_component，传入当前图数据进行渲染:", st.session_state.current_graph)  # Debug输出当前图数据
        graph = graph_component(graph=st.session_state.current_graph, component="graph", key="graph_editor")  # 将当前图数据传入自定义组件进行渲染和编辑
        # st.write("graph_component调用完成，graph:", graph)  # Debug输出当前图数据
        if graph:
            if "user_edges" in graph:
                st.session_state.current_graph["user_edges"] = graph["user_edges"]  # 更新用户连线数据
    else:
        # st.header("AI Learning Assistant")
        chat_container = st.container(height=640)
        with chat_container:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
        
        if prompt := st.chat_input("Ask questions about the literature..."):
            st.session_state.chat_history.append({"role": "user", "content": str(prompt)})
            # with st.chat_message("user"):
            #     st.markdown(prompt)
            st.rerun()
        if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
            status_placeholder.info("AI is thinking...")
            
            all_notes = "\n".join([f"- {note}" for notes in st.session_state.notes.values() for note in notes])
            graph_text = format_graph_for_llm(st.session_state.current_graph)
            system_prompt = f"""
                你是一名教育技术学专家，帮助学生理解这篇以“VR学习中的提示策略”为主题的文献。以下是文献的主要内容、学生从文献中提取的笔记和构建的思维导图内容：

                【文献内容摘要】
                {"Virtual Reality (VR) provides immersive learning experiences that can potentially promote learning motivation and performance; however, high spatial presence in VR may impair cognitive and perceptual processing due to resource overload. While current perspectives on multimedia learning emphasize the important role of cognitive and metacognitive strategies, recent studies have suggested that high-immersion VR may, in some cases, be less effective in terms of supporting student learning. Moreover, prior research has depicted distinct learning effects of cognitive and metacognitive prompts. Some studies have declared that cognitive prompts, alone or combined with metacognitive prompts, enhance learning outcomes more than metacognitive prompts alone, while others have highlighted the greater advantages of their combination compared to cognitive prompts alone. A game-based VR learning system with cognitive and metacognitive strategies was designed in this study to support students’ inquiry-based science learning activities, and to examine their individual and interaction effects on learning outcomes. A two-factor experimental design was adopted to address the research questions assessing the effects of this approach on students’ science learning achievements, problem-solving tendencies, and self-efficacy. Furthermore, four groups of students aged between 10 and 11 years old participated in the experiment, each following different prompt conditions: cognitive (cognitive vs. non-cognitive) and metacognitive (metacognitive vs. non-metacognitive) mechanisms during the game-based VR learning activities. Results indicated that students learning with cognitive prompts but without metacognitive prompts displayed better learning achievements and stronger problem-solving tendencies compared to those with no prompts. Moreover, students using only cognitive prompts displayed significantly stronger problem-solving tendencies than those utilizing both cognitive and metacognitive prompts. Furthermore, students with cognitive prompts revealed higher self-efficacy than those without cognitive prompts. This study offers new insights into the roles of cognitive and metacognitive strategies in game-based VR learning, highlighting the potential benefits of cognitive prompts for supporting multimedia learning within highimmersion environments."}

                【已有笔记】
                {all_notes}

                【思维导图内容】
                {graph_text}

                请基于以上信息回答学生的问题，并满足：
                1.引用与问题高相关的学生笔记内容和思维导图内容，如果没有高相关就不引用，但必须准确回答学生的问题
                2.尽量引用学生{graph_text}中的与问题高相关关系，并提出对于已有节点之间的关系的优化和补充建议，不要提出不存在的节点
                3.鼓励学生发现不同模块之间的联系
            """
            try:
                with st.spinner("Generating answer..."):
                    # st.write("DEBUG prompt type:", type(prompt))
                    # st.write("DEBUG prompt value:", prompt)
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "system", "content": system_prompt}, *st.session_state.chat_history],
                        temperature=0.3
                    )
                    answer = response.choices[0].message.content or "Sorry, I couldn't generate an answer."
                    st.session_state.chat_history.append({"role": "assistant", "content": str(answer)})
                    st.session_state.status_type = "success"
                    st.session_state.status_msg = "Answer generated successfully!"
                    st.rerun()
            except Exception as e:
                st.error(f"API call failed: {e}")
if (st.session_state.task_queue and not st.session_state.is_processing):
    st.session_state.is_processing = True
    status_placeholder.info("Grasping meaning and Generating mind map...")
    
    task = st.session_state.task_queue[0]
    if task["type"] == "graph":
        new_graph = generate_mind_map(
            task["text"],
            {
                "nodes": st.session_state.current_graph["nodes"],
                "edges": st.session_state.current_graph["edges"]
            },
            task["category"])
        if new_graph:
            st.session_state.current_graph["nodes"] = new_graph["nodes"]
            st.session_state.current_graph["edges"] = new_graph["edges"]
            st.session_state.task_queue.pop(0)  # 移除已完成的任务
            st.session_state.status_type = "success"
            st.session_state.status_msg = "Mind map generated successfully!"
    st.session_state.is_processing = False
    st.rerun()