import React, { useEffect, useRef } from 'react';
import { Streamlit, withStreamlitConnection } from 'streamlit-component-lib';

window.renderCount = (window.renderCount || 0) + 1;
console.log("渲染次数:", window.renderCount);

function PdfViewer({ args }) {
  console.log("当前args:", args);
  const containerRef = useRef(null);
  useEffect(() => {
    console.log("React组件已加载");
    console.log("接收的args:", args);
    // console.log("接收的props完整结构:", JSON.stringify(props));

    Streamlit.setComponentReady();
    if (!args || !args.base64_pdf) {
      console.error("未找到base64_pdf参数");
      return;
    }
    const base64_pdf = args.base64_pdf;
    console.log("接收到的base64_pdf前50字符:", base64_pdf.slice(0, 50));

    const pdfData = atob(base64_pdf);
    let selectedRange = null;
    let selectedText = "";
    
    const container = containerRef.current;
    const style = document.createElement('style');

    container.innerHTML = `
      <div id="viewer"></div>
      <!-- 划线笔记弹窗 -->
      <div id="popup">
        <select id="category">
            <option value="自动识别">自动识别</option>
            <option value="研究背景">研究背景</option>
            <option value="研究问题">研究问题</option>
            <option value="研究方法">研究方法</option>
            <option value="研究结论">研究结论</option>
        </select>
        <button id="saveBtn">保存划线笔记</button>
      </div>
    `;
    
    style.innerHTML = `
      #viewer {
        position: relative;
        height: 700px;
        overflow: auto;
        border: 1px solid #ccc;
      }
      .page{
        position: relative;
        margin-bottom: 10px;
      }
      .textLayer{
        position: absolute;
        color: transparent;
        left: 0;
        top: 0;
        right: 0;
        bottom: 0;
        pointer-events: auto;
      }
      .textLayer span{
        position: absolute;
        white-space: pre;
        transform-origin: 0 0;
        pointer-events: auto;
      }
      .highlight{
        position: absolute;
        background: rgba(255, 214, 102, 0.6);
        mix-blend-mode: multiply;
        pointer-events: none;
        z-index: 100;
      }
      #popup{
        position: fixed;
        display: none;
        background: white;
        border: 1px solid #ccc;
        padding: 8px;
        z-index: 999;                            
      } 
    `;
    document.head.appendChild(style);

    Streamlit.setFrameHeight(800);
    //========PDF渲染==========//
    function loadPDF() {
      const pdfjsLib = window['pdfjsLib'];
      pdfjsLib.getDocument({data: pdfData}).promise.then(pdf => {
        for(let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
          pdf.getPage(pageNum).then(page => {
            const viewport = page.getViewport({scale: 1.0});
            const div = document.createElement('div');
            div.style.position = 'relative';
            div.style.width = viewport.width + 'px';
            div.style.height = viewport.height + 'px';
                
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            canvas.style.width = viewport.width + 'px';
            canvas.style.height = viewport.height + 'px';
            div.appendChild(canvas);

            const textLayer = document.createElement('div');
            textLayer.className = 'textLayer';
            textLayer.style.position = 'absolute';
            textLayer.style.top = '0';
            textLayer.style.left = '0';
            div.appendChild(textLayer);
            document.getElementById('viewer').appendChild(div);

            page.render({canvasContext: ctx, viewport: viewport});
            page.getTextContent().then(textContent => {
              pdfjsLib.renderTextLayer({
                textContent: textContent,
                container: textLayer,
                viewport: viewport,
              });
            });
          });
        }
      });
    };

    if (!window['pdfjsLib']) {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.10.377/pdf.min.js';
      script.onload = loadPDF;
      document.body.appendChild(script);
    } else {
      loadPDF();
    }

    //========划线监听==========//
    const handleMouseUp = (e) => {
      const selection = window.getSelection();
      const text = selection.toString().trim();
      if(text) {
          selectedRange = selection.getRangeAt(0);
          selectedText = text;
          // 显示笔记弹窗
          const popup = document.getElementById('popup');
          popup.style.left = e.pageX + 'px';
          popup.style.top = e.pageY + 'px';
          popup.style.display = 'block';
          console.log("Selected text:", selectedText);
      } 
    };
    document.addEventListener('mouseup', handleMouseUp);

    //========高亮选中文本==========//
    function highlightSelection(rects) {
      const viewer = document.getElementById('viewer');
      const viewerRect = viewer.getBoundingClientRect();
      rects = Array.from(rects);
      rects.forEach(rect => {
          const highlight = document.createElement('div');
          highlight.className = 'highlight';
          highlight.style.left = rect.left - viewerRect.left + viewer.scrollLeft + 'px';
          highlight.style.top = rect.top - viewerRect.top + viewer.scrollTop + 'px';
          highlight.style.width = rect.width + 'px';
          highlight.style.height = rect.height + 'px';
          viewer.appendChild(highlight);
      });
    }

    //========保存笔记==========//
    const handleClick = (e) => {
      if (e.target.id === 'saveBtn') {
        if (!selectedRange) return;
        //高亮原文
        highlightSelection(selectedRange.getClientRects());

        const category = document.getElementById("category").value;
        const noteData = {
            text: selectedText,
            category: category
        };
        console.log("传送:", noteData);
        if (selectedText) {
          Streamlit.setComponentValue(noteData);
        }

        //隐藏弹窗
        document.getElementById("popup").style.display = "none";
        window.getSelection().removeAllRanges();
      }
    };
    document.addEventListener('click', handleClick);

    return () => {
       console.log("cleanup执行");
       document.removeEventListener('mouseup', handleMouseUp);
       document.removeEventListener('click', handleClick);
      if (container) {
        container.innerHTML = '';
      };
    };
  },[args.base64_pdf]);

  return <div ref={containerRef}></div>;
}
export default withStreamlitConnection(PdfViewer);