import type { ReactNode } from "react";
import { useMemo, useState } from "react";

interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  rows: T[];
  columns: Array<Column<T>>;
  empty: string;
  maxRows?: number;
  enableColumnControls?: boolean;
}

export function DataTable<T>({ rows, columns, empty, maxRows = 1000, enableColumnControls = false }: DataTableProps<T>) {
  const [hiddenColumns, setHiddenColumns] = useState<string[]>([]);
  const visibleColumns = useMemo(() => columns.filter((column) => !hiddenColumns.includes(column.key)), [columns, hiddenColumns]);
  const visibleRows = rows.slice(0, maxRows);
  if (!rows.length) {
    return <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-5 text-center text-xs text-slate-500">{empty}</div>;
  }
  return (
    <div className="rounded-md border border-slate-200">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600">
        <span>{rows.length} rows{visibleRows.length < rows.length ? `; showing ${visibleRows.length}` : ""}</span>
        {enableColumnControls ? (
          <details className="ml-auto">
            <summary className="cursor-pointer">Columns</summary>
            <div className="absolute z-10 mt-1 grid max-h-64 min-w-56 gap-1 overflow-auto rounded-md border border-slate-200 bg-white p-2 shadow">
              {columns.map((column) => (
                <label key={column.key} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={!hiddenColumns.includes(column.key)}
                    onChange={(event) =>
                      setHiddenColumns((current) => (event.target.checked ? current.filter((key) => key !== column.key) : [...current, column.key]))
                    }
                  />
                  {column.header}
                </label>
              ))}
            </div>
          </details>
        ) : null}
      </div>
      <div className="thin-scrollbar max-h-[28rem] overflow-auto">
      <table className="w-full min-w-[44rem] border-collapse text-left text-[11px]">
        <thead className="sticky top-0 z-[1] bg-slate-100 text-[10px] font-semibold uppercase text-slate-600">
          <tr>
            {visibleColumns.map((column) => (
              <th key={column.key} className={`border-b border-slate-200 px-2 py-2 ${column.className ?? ""}`}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-b border-slate-100 last:border-b-0 hover:bg-slate-50">
              {visibleColumns.map((column) => (
                <td key={column.key} className={`px-2 py-1 align-top text-slate-700 ${column.className ?? ""}`}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
