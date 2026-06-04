import { useEffect } from "react";
import { loader } from "@monaco-editor/react";
import type { Monaco } from "@monaco-editor/react";

loader.config({
  paths: {
    vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.0/min/vs",
  },
});

export function useMonacoSetup() {
  useEffect(() => {
    loader.init().then((monaco: Monaco) => {
      // Custom theme for Construct
      monaco.editor.defineTheme("construct-dark", {
        base: "vs-dark",
        inherit: true,
        rules: [
          { token: "comment", foreground: "6c7086", fontStyle: "italic" },
          { token: "keyword", foreground: "cba6f7" },
          { token: "identifier", foreground: "cdd6f4" },
          { token: "string", foreground: "a6e3a1" },
          { token: "number", foreground: "fab387" },
          { token: "tag", foreground: "89b4fa" },
          { token: "attribute.name", foreground: "f9e2af" },
          { token: "attribute.value", foreground: "a6e3a1" },
          { token: "type", foreground: "f9e2af" },
        ],
        colors: {
          "editor.background": "#0a0a0f",
          "editor.foreground": "#f1f5f9",
          "editor.lineHighlightBackground": "#22222f55",
          "editor.selectionBackground": "#3a3a4f",
          "editor.inactiveSelectionBackground": "#2d2d3d",
          "editorCursor.foreground": "#6366f1",
          "editorLineNumber.foreground": "#64748b",
          "editorLineNumber.activeForeground": "#f1f5f9",
          "editor.selectionHighlightBackground": "#3a3a4f44",
          "editor.wordHighlightBackground": "#3a3a4f44",
          "editor.wordHighlightStrongBackground": "#3a3a4f66",
          "editorWidget.background": "#12121a",
          "editorWidget.border": "#22222f",
          "editorSuggestWidget.background": "#12121a",
          "editorSuggestWidget.border": "#22222f",
          "editorSuggestWidget.selectedBackground": "#3a3a4f",
          "editorSuggestWidget.highlightForeground": "#6366f1",
          "editorBracketMatch.background": "#3a3a4f66",
          "editorBracketMatch.border": "#6366f1",
        },
      });
    });
  }, []);
}

export default useMonacoSetup;
