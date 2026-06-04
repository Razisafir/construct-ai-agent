import { useRef } from "react";

export interface Column<T> {
  key: string;
  header: string;
  width?: string;
  render?: (row: T) => React.ReactNode;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  selectedId?: string;
  onSelect?: (row: T) => void;
  keyExtractor: (row: T) => string;
}

const BASE = "#0c0c10";
const S1 = "#12121a";
const S2 = "#1a1a24";
const S3 = "#22222e";
const ACCENT = "#6366f1";
const TEXT = "#e8e8ec";

const TEXT_DIM = "#6b6b73";
const BORDER = "rgba(255,255,255,0.04)";

export default function DataTable<T>({
  columns,
  data,
  selectedId,
  onSelect,
  keyExtractor,
}: DataTableProps<T>) {
  const tbodyRef = useRef<HTMLDivElement>(null);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        overflow: "hidden",
        fontFamily: '"Geist Mono", "JetBrains Mono", monospace',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          borderBottom: `1px solid ${BORDER}`,
          background: S1,
          flexShrink: 0,
        }}
      >
        {columns.map((col) => (
          <div
            key={col.key}
            style={{
              width: col.width || "auto",
              flex: col.width ? undefined : 1,
              padding: "6px 8px",
              fontSize: "10px",
              fontWeight: 500,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: TEXT_DIM,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {col.header}
          </div>
        ))}
      </div>

      {/* Rows */}
      <div
        ref={tbodyRef}
        style={{
          flex: 1,
          overflow: "auto",
          scrollbarWidth: "thin",
          scrollbarColor: `${S3} transparent`,
        }}
      >
        {data.length === 0 && (
          <div
            style={{
              padding: "32px 8px",
              textAlign: "center",
              fontSize: "11px",
              color: TEXT_DIM,
            }}
          >
            No data
          </div>
        )}
        {data.map((row) => {
          const id = keyExtractor(row);
          const isSelected = selectedId === id;
          return (
            <div
              key={id}
              onClick={() => onSelect?.(row)}
              style={{
                display: "flex",
                alignItems: "center",
                cursor: onSelect ? "pointer" : "default",
                background: isSelected ? S2 : BASE,
                borderLeft: isSelected
                  ? `2px solid ${ACCENT}`
                  : "2px solid transparent",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) {
                  (e.currentTarget as HTMLDivElement).style.background = S2;
                }
              }}
              onMouseLeave={(e) => {
                if (!isSelected) {
                  (e.currentTarget as HTMLDivElement).style.background = BASE;
                }
              }}
            >
              {columns.map((col) => (
                <div
                  key={col.key}
                  style={{
                    width: col.width || "auto",
                    flex: col.width ? undefined : 1,
                    padding: "6px 8px",
                    fontSize: "11px",
                    color: TEXT,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {col.render
                    ? col.render(row)
                    : String((row as Record<string, unknown>)[col.key] ?? "")}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
