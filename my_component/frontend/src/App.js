import React from "react";
import PdfViewer from "./components/PdfViewer";
import GraphViewer from "./components/GraphViewer";
import { withStreamlitConnection } from "streamlit-component-lib";

function App({ args }) {
  console.log("App组件接收到的args:", args);
  if (args.component === "pdf") {
    return <PdfViewer args={args} />;
  }
  else if (args.component === "graph") {
    console.log("渲染GraphViewer组件，传入args:", args);
    return <GraphViewer args={args} />;
  }
  else {
    return <div>Unsupported mode: {args.component}</div>;
  }
}

export default withStreamlitConnection(App);