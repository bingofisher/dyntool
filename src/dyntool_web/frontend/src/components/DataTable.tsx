type DataTableProps = {
  title: string;
  columns: string[];
  rows: string[][];
  emptyText?: string;
  totalText?: string;
};

export const DataTable = ({ title, columns, rows, emptyText = "暂无数据", totalText }: DataTableProps) => (
  <section className="table-card">
    <header className="section-header">
      <strong>{title}</strong>
      {rows.length ? <span>{`${rows.length} 行 / 列数 ${columns.length}${totalText ? ` / ${totalText}` : ""}`}</span> : null}
    </header>
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row, rowIndex) => (
              <tr key={`${row.join("-")}-${rowIndex}`}>
                {columns.map((column, columnIndex) => (
                  <td key={`${column}-${columnIndex}`}>{row[columnIndex] ?? ""}</td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={Math.max(columns.length, 1)} className="empty-cell">
                {emptyText}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  </section>
);
