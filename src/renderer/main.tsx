import React, { Suspense } from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import "./index.css";

const C = {
  base: "#0c0e11",
  s1: "#141619",
  s3: "#282a2d",
  accent: "#00f5ff",
  text: "#e2e2e6",
  t3: "#849495",
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HashRouter>
      <ErrorBoundary>
        <Suspense fallback={<LoadingScreen />}>
          <App />
        </Suspense>
      </ErrorBoundary>
    </HashRouter>
  </React.StrictMode>
);

function LoadingScreen() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        height: "100%",
        background: C.base,
        gap: "16px",
        fontFamily: '"JetBrains Mono", monospace',
      }}
    >
      <div
        style={{
          width: "24px",
          height: "24px",
          border: `2px solid ${C.accent}`,
          borderTopColor: "transparent",
          borderRadius: "50%",
          animation: "spin 1s linear infinite",
        }}
      />
      <span style={{ fontSize: "11px", color: C.t3 }}>Loading Construct...</span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
