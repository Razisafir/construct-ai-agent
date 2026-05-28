import React, { Suspense } from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import "./index.css";

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
    <div className="flex flex-col items-center justify-center w-full h-full bg-construct-bg-primary gap-4">
      <div className="w-10 h-10 border-2 border-construct-accent-primary border-t-transparent rounded-full animate-spin" />
      <span className="text-sm text-construct-text-muted">Loading Construct...</span>
    </div>
  );
}
