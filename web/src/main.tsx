import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
/* 自托管字体：MiSans（中文正文）、Space Grotesk（拉丁品牌字）、JetBrains Mono（元数据） */
import "@fontsource-variable/space-grotesk";
import "@fontsource-variable/jetbrains-mono";
import "misans/lib/Normal/MiSans-Regular.min.css";
import "misans/lib/Normal/MiSans-Medium.min.css";
import "misans/lib/Normal/MiSans-Demibold.min.css";
import "misans/lib/Normal/MiSans-Bold.min.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
