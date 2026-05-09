import { useMemo } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { json } from "@codemirror/lang-json";
import { oneDark } from "@codemirror/theme-one-dark";
import { EditorView } from "@codemirror/view";
import { useUiStore } from "@/lib/state/ui-store";

export interface JsonViewProps {
  value: unknown;
  height?: string;
  maxHeight?: string;
}

const READ_ONLY_EXTENSIONS = [json(), EditorView.editable.of(false), EditorView.lineWrapping];

export function JsonView({ value, height, maxHeight }: JsonViewProps) {
  const theme = useUiStore((s) => s.theme);
  const text = useMemo(() => safeStringify(value), [value]);

  return (
    <CodeMirror
      value={text}
      height={height}
      maxHeight={maxHeight}
      theme={theme === "dark" ? oneDark : "light"}
      extensions={READ_ONLY_EXTENSIONS}
      basicSetup={{
        lineNumbers: true,
        foldGutter: true,
        highlightActiveLine: false,
        highlightActiveLineGutter: false,
      }}
      readOnly
    />
  );
}

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
