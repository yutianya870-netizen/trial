import React, { use, useCallback, useEffect, useState } from 'react';
import { Streamlit, withStreamlitConnection } from 'streamlit-component-lib';
import ReactFlow, { addEdge, Controls, Background } from "react-flow-renderer";
import "react-flow-renderer-gd/dist/style.css"
import dagre from "dagre";

//========== dagre自动布局函数 ============//
const nodeWidth = 180;
const nodeHeight = 60;

const getLayoutedElements = (nodes, edges, direction = "LR") => {
    const isHorizontal = direction === "LR";
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({ rankdir: direction });
    
    //注册节点
    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
    });

    //注册边
    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        node.targetPosition = isHorizontal ? "left" : "top";
        node.sourcePosition = isHorizontal ? "right" : "bottom";
        return {
            ...node,
            position: {
                x: nodeWithPosition.x - nodeWidth / 2,
                y: nodeWithPosition.y - nodeHeight / 2,
            },
        };
    });
    return { nodes: layoutedNodes, edges };
}

function GraphViewer({ args }) {
    //初始化页面,只执行一次
    useEffect(() => {
        Streamlit.setComponentReady();
        Streamlit.setFrameHeight(800);  // 设置组件高度，确保有足够空间显示图
    }, [])

    const [nodes, setNodes] = useState([]);
    const [edges, setEdges] = useState([]);
    const [userEdges, setUserEdges] = useState([]); // 用于存储用户连线

    useEffect(() => {
        if (!args.graph) return;
        // const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(args.graph.nodes || [], args.graph.edges || [], "TB");
        // setNodes(layoutedNodes);
        // setEdges(layoutedEdges);
        const structuredNodes = args.graph.nodes || [];
        const structuredEdges = args.graph.edges || [];
        const userEdegesFromPy = args.graph.user_edges || [];
        const Nodes = getLayoutedElements(structuredNodes, structuredEdges, "LR").nodes;
        const styledStructureEdges = structuredEdges.map((e) => ({ 
            ...e, 
            type: "structure", 
            style: { stroke: "#222" } 
        }));
        const styledUserEdges = userEdegesFromPy.map((e) => ({
            ...e,
            type: "user",
            style: { stroke: "red"},
            animated: true, // 用户连线添加动画效果
        }));
        setNodes(Nodes);
        // setEdges([...styledStructureEdges, ...styledUserEdges]);
        setEdges((prevEdges) => {
            const prevUserEdges = prevEdges.filter((e) => e.type === "user");
            if (styledUserEdges.length < prevUserEdges.length) {
                console.log("忽略后端旧数据，防止UI回退");
                return prevEdges;
            }
            return [...styledStructureEdges, ...styledUserEdges];
        });
        setUserEdges(styledUserEdges);
    }, [args.graph])

    //用户连线
    const onConnect = useCallback((params) => {
        console.log("触发连接:", params);
        const label = window.prompt("请输入关系名称：")?.trim();
        const newUserEdges = {
            ...params,
            id: `user-edge-${Date.now()}`,
            type: "user",
            label: label || "相关",
            style: { stroke: "red" },
            animated: true,
        };

        setUserEdges((prev) => {
            const updatedUserEdges = [...prev, newUserEdges];
            console.log("更新后的用户连线数据:", updatedUserEdges);
            Streamlit.setComponentValue({ user_edges: updatedUserEdges });
            return updatedUserEdges;
        });
        
        //立即更新UI的edges状态以反映用户的连线操作，同时通过Streamlit.setComponentValue将更新后的用户连线数据传回Python端，确保前后端数据同步
        setEdges((prevEdges) => [...prevEdges, newUserEdges]); 
    }, [])

    const onEdgeClick = useCallback((event, edge) => {
        if (edge.type === "user") {
            const newLabel = window.prompt("编辑关系名称：", edge.label || "相关").trim();
            if (newLabel == null) return;

            setUserEdges((prev) => {
                const updatedUserEdges = prev.map((e) => 
                    e.id === edge.id ? { ...e, label: newLabel } : e
                );
                Streamlit.setComponentValue({ user_edges: updatedUserEdges });
                return updatedUserEdges;
            });

            setEdges((prevEdges) => 
                prevEdges.map((e) => 
                    e.id === edge.id ? { ...e, label: newLabel } : e
                )
            );
        }
    }, []);

    return(
    <div style={{ width: "100%", height: "700px"}}>
    <ReactFlow
        nodes={nodes}
        edges={edges}
        onConnect={onConnect}
        onEdgeClick={onEdgeClick}
        fitView //自动缩放到视图
    >
        <Controls />
        <Background />
    </ReactFlow>
    </div>
    );
}
    export default withStreamlitConnection(GraphViewer);