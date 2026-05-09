import { useMemo } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { json } from "@codemirror/lang-json";
import { oneDark } from "@codemirror/theme-one-dark";
import { EditorView } from "@codemirror/view";
import { useUiStore } from "@/lib/state/ui-store";
import { maskPayloadFields } from "@/lib/privacy/mask";

export interface JsonViewProps {
  value: unknown;
  height?: string;
  maxHeight?: string;
}

const READ_ONLY_EXTENSIONS = [json(), EditorView.editable.of(false), EditorView.lineWrapping];

export function JsonView({ value, height, maxHeight }: JsonViewProps) {
  const theme = useUiStore((s) => s.theme);
  const masked = useUiStore((s) => s.payloadVisibility === "masked");
  const text = useMemo(
    () => safeStringify(masked ? maskedDeep(value) : value),
    [value, masked],
  );

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

function maskedDeep(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(maskedDeep);
  if (value !== null && typeof value === "object") {
    return maskPayloadFields(
      Object.fromEntries(
        Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, maskedDeep(v)]),
      ),
    );
  }
  return value;
}
