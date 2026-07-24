import { useEffect, useRef, useState } from 'react';
import { Columns3, GripVertical, Minus, Pencil, Plus, Rows3 } from 'lucide-react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { TiptapInlineEditor } from './TiptapEditor';

const COLORS = ['#14b8a6', '#6366f1', '#f59e0b', '#ec4899', '#22c55e', '#38bdf8', '#f97316', '#a855f7'];

function DraggableActions({ children, className = '' }) {
  const toolbarRef = useRef(null);
  const dragRef = useRef(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const move = (event) => {
      const drag = dragRef.current;
      const toolbar = toolbarRef.current;
      if (!drag || !toolbar) return;
      const slide = toolbar.closest('.element-canvas, .editable-slide-root');
      if (!slide) return;
      const slideRect = slide.getBoundingClientRect();
      const toolbarRect = toolbar.getBoundingClientRect();
      const requestedX = drag.offset.x + event.clientX - drag.pointer.x;
      const requestedY = drag.offset.y + event.clientY - drag.pointer.y;
      const minX = drag.offset.x + slideRect.left + 8 - toolbarRect.left;
      const maxX = drag.offset.x + slideRect.right - 8 - toolbarRect.right;
      const minY = drag.offset.y + slideRect.top + 8 - toolbarRect.top;
      const maxY = drag.offset.y + slideRect.bottom - 8 - toolbarRect.bottom;
      setOffset({
        x: Math.min(maxX, Math.max(minX, requestedX)),
        y: Math.min(maxY, Math.max(minY, requestedY)),
      });
    };
    const stop = () => {
      dragRef.current = null;
      document.body.classList.remove('sv-toolbar-dragging');
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop);
    window.addEventListener('pointercancel', stop);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
      window.removeEventListener('pointercancel', stop);
    };
  }, []);

  const startDrag = (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragRef.current = {
      pointer: { x: event.clientX, y: event.clientY },
      offset,
    };
    document.body.classList.add('sv-toolbar-dragging');
  };

  return (
    <div
      ref={toolbarRef}
      className={`sv-data-actions ${className}`}
      style={{ transform: `translate3d(${offset.x}px, ${offset.y}px, 0)` }}
    >
      <button type="button" className="sv-action-drag" onPointerDown={startDrag}
        onDoubleClick={() => setOffset({ x: 0, y: 0 })} title="Kéo thanh công cụ" aria-label="Kéo thanh công cụ">
        <GripVertical size={14} />
      </button>
      {children}
    </div>
  );
}

function cleanRows(table) {
  const headers = Array.isArray(table?.headers) ? table.headers.map(String) : [];
  const rows = Array.isArray(table?.rows) ? table.rows : [];
  const headerHtml = Array.isArray(table?.headerHtml) ? table.headerHtml : [];
  const cellHtml = Array.isArray(table?.cellHtml) ? table.cellHtml : [];
  const headerStyles = Array.isArray(table?.headerStyles) ? table.headerStyles : [];
  const cellStyles = Array.isArray(table?.cellStyles) ? table.cellStyles : [];
  return { headers, rows: rows.map((row) => Array.isArray(row) ? row : []), headerHtml, cellHtml, headerStyles, cellStyles };
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function plainTextFromHtml(html) {
  const container = document.createElement('div');
  container.innerHTML = String(html || '');
  return (container.textContent || '').replace(/\s+/g, ' ').trim();
}

function removeConflictingInlineStyles(html, patch) {
  if (!html) return html;
  const propertyMap = {
    fontFamily: 'font-family',
    fontSize: 'font-size',
    color: 'color',
    fontWeight: 'font-weight',
    fontStyle: 'font-style',
    textDecoration: 'text-decoration',
    textAlign: 'text-align',
    lineHeight: 'line-height',
  };
  const properties = Object.keys(patch || {}).map((key) => propertyMap[key]).filter(Boolean);
  if (!properties.length) return html;
  const container = document.createElement('div');
  container.innerHTML = String(html);
  container.querySelectorAll('[style]').forEach((node) => {
    properties.forEach((property) => node.style.removeProperty(property));
    if (!node.getAttribute('style')?.trim()) node.removeAttribute('style');
  });
  return container.innerHTML;
}

function TableCellEditor({ value, html, editable, elementKey, onSave, style = {}, onStyleChange, onPointerDown, onPointerEnter, rangeSelected, batchMode, baseFontSize }) {
  const justifyContent = {
    top: 'flex-start',
    middle: 'center',
    bottom: 'flex-end',
  }[style.verticalAlign] || 'center';
  return (
    <TiptapInlineEditor
      value={html || escapeHtml(value)}
      editable={editable}
      elementKey={elementKey}
      className="sv-cell-editor"
      style={{
        ...style,
        display: 'flex',
        flexDirection: 'column',
        justifyContent,
        background: rangeSelected ? 'rgba(108,99,255,.13)' : style.background,
        boxShadow: rangeSelected ? 'inset 0 0 0 2px #6c63ff' : style.boxShadow,
      }}
      onPointerDown={onPointerDown}
      onPointerEnter={onPointerEnter}
      boxStyle={style}
      onBoxStyleChange={onStyleChange}
      batchMode={batchMode}
      autoFit
      autoFitBaseFontSize={Number(style.fontSize) || baseFontSize}
      placeholder="Nhập nội dung"
      minFontSize={6}
      onSave={onSave}
    />
  );
}

export function TableVisual({ table, theme, onChange, onInteract }) {
  const { headers, rows, headerHtml, cellHtml, headerStyles, cellStyles } = cleanRows(table);
  const tableRef = useRef(null);
  const [columnWidths, setColumnWidths] = useState(
    Array.isArray(table?.columnWidths) && table.columnWidths.length === headers.length ? table.columnWidths : [],
  );
  const [rowHeights, setRowHeights] = useState(
    Array.isArray(table?.rowHeights) && table.rowHeights.length === rows.length + 1 ? table.rowHeights : [],
  );
  const [cellRange, setCellRange] = useState(null);
  const cellRangeRef = useRef(null);
  const selectingRef = useRef(false);
  const visibleRows = rows.slice(0, 8);
  const density = Math.max(headers.length, rows.length);
  const totalChars = [...headers, ...rows.flat()].reduce((sum, value) => sum + String(value ?? '').length, 0);
  const tableFontSize = totalChars > 1100
    ? 8
    : totalChars > 760 || density >= 8 || headers.length >= 6
      ? 9
      : totalChars > 480 || density >= 6
        ? 10.5
        : 13;
  const visibleRowWeights = rowHeights.length === rows.length + 1
    ? rowHeights.slice(0, visibleRows.length + 1).map((value) => Math.max(28, Number(value) || 28))
    : Array.from({ length: visibleRows.length + 1 }, () => 1);
  const visibleColumnWeights = headers.map((_, index) => Math.max(1, Number(columnWidths[index]) || 1));
  const tableGridStyle = {
    color: theme.text,
    fontFamily: theme.fontBody,
    gridTemplateColumns: visibleColumnWeights.map((value) => `${value}fr`).join(' '),
    gridTemplateRows: visibleRowWeights.map((value) => `${value}fr`).join(' '),
  };
  useEffect(() => {
    if (Array.isArray(table?.columnWidths) && table.columnWidths.length === headers.length) {
      setColumnWidths(table.columnWidths.map(Number));
    } else {
      setColumnWidths([]);
    }
  }, [headers.length, table?.columnWidths]);
  useEffect(() => {
    if (Array.isArray(table?.rowHeights) && table.rowHeights.length === rows.length + 1) {
      setRowHeights(table.rowHeights.map(Number));
    } else {
      setRowHeights([]);
    }
  }, [rows.length, table?.rowHeights]);
  useEffect(() => {
    const stopSelection = () => {
      selectingRef.current = false;
      document.body.classList.remove('sv-cell-range-selecting');
      const anchor = cellRangeRef.current?.start;
      if (anchor) {
        const key = anchor.row === 0
          ? `table-header-${anchor.col}`
          : `table-cell-${anchor.row - 1}-${anchor.col}`;
        window.requestAnimationFrame(() => {
          tableRef.current?.querySelector(`[data-slide-element="${key}"]`)?.click();
        });
      }
    };
    window.addEventListener('pointerup', stopSelection);
    window.addEventListener('pointercancel', stopSelection);
    return () => {
      window.removeEventListener('pointerup', stopSelection);
      window.removeEventListener('pointercancel', stopSelection);
      document.body.classList.remove('sv-cell-range-selecting');
    };
  }, []);
  const beginCellSelection = (event, row, col) => {
    if (!onChange || event.button !== 0 || event.target.closest('.is-editing')) return;
    event.stopPropagation();
    onInteract?.();
    selectingRef.current = true;
    document.body.classList.add('sv-cell-range-selecting');
    setCellRange((current) => {
      const next = event.shiftKey && current
        ? { start: current.start, end: { row, col } }
        : { start: { row, col }, end: { row, col } };
      cellRangeRef.current = next;
      return next;
    });
  };
  const extendCellSelection = (row, col) => {
    if (!selectingRef.current) return;
    setCellRange((current) => {
      const next = current ? { ...current, end: { row, col } } : current;
      cellRangeRef.current = next;
      return next;
    });
  };
  const isCellSelected = (row, col) => {
    if (!cellRange) return false;
    const minRow = Math.min(cellRange.start.row, cellRange.end.row);
    const maxRow = Math.max(cellRange.start.row, cellRange.end.row);
    const minCol = Math.min(cellRange.start.col, cellRange.end.col);
    const maxCol = Math.max(cellRange.start.col, cellRange.end.col);
    return row >= minRow && row <= maxRow && col >= minCol && col <= maxCol;
  };
  const rangeCellCount = cellRange
    ? (Math.abs(cellRange.start.row - cellRange.end.row) + 1)
      * (Math.abs(cellRange.start.col - cellRange.end.col) + 1)
    : 0;
  const pasteCellMatrix = (event) => {
    if (!onChange || !cellRange || event.target.closest('.is-editing')) return;
    const text = event.clipboardData?.getData('text/plain') || '';
    if (!text || (!text.includes('\t') && !/[\r\n]/.test(text))) return;
    event.preventDefault();
    event.stopPropagation();
    const matrix = text
      .replace(/\r/g, '')
      .split('\n')
      .filter((line, index, lines) => line.length || index < lines.length - 1)
      .map((line) => line.split('\t'));
    if (!matrix.length) return;
    const startRow = Math.min(cellRange.start.row, cellRange.end.row);
    const startCol = Math.min(cellRange.start.col, cellRange.end.col);
    const nextHeaders = [...headers];
    const nextRows = rows.map((row) => [...row]);
    const nextHeaderHtml = [...headerHtml];
    const nextCellHtml = cellHtml.map((row) => Array.isArray(row) ? [...row] : []);
    const requiredColumns = startCol + Math.max(...matrix.map((row) => row.length));
    while (nextHeaders.length < requiredColumns) nextHeaders.push(`Cột ${nextHeaders.length + 1}`);
    nextRows.forEach((row) => {
      while (row.length < requiredColumns) row.push('');
    });
    matrix.forEach((values, matrixRow) => {
      const targetRow = startRow + matrixRow;
      if (targetRow === 0) {
        values.forEach((value, offset) => {
          nextHeaders[startCol + offset] = value;
          nextHeaderHtml[startCol + offset] = escapeHtml(value);
        });
        return;
      }
      while (nextRows.length < targetRow) {
        nextRows.push(nextHeaders.map(() => ''));
        nextCellHtml.push([]);
      }
      values.forEach((value, offset) => {
        nextRows[targetRow - 1][startCol + offset] = value;
        while (nextCellHtml.length < targetRow) nextCellHtml.push([]);
        nextCellHtml[targetRow - 1][startCol + offset] = escapeHtml(value);
      });
    });
    onChange({
      ...table,
      headers: nextHeaders,
      rows: nextRows,
      headerHtml: nextHeaderHtml,
      cellHtml: nextCellHtml,
      columnWidths: nextHeaders.length === headers.length ? columnWidths : [],
      rowHeights: nextRows.length === rows.length ? rowHeights : [],
    });
  };
  const startColumnResize = (event, index) => {
    if (!onChange || index >= headers.length - 1) return;
    event.preventDefault();
    event.stopPropagation();
    const cells = [...(tableRef.current?.querySelectorAll('thead th') || [])];
    const initial = columnWidths.length === headers.length
      ? [...columnWidths]
      : cells.map((cell) => cell.getBoundingClientRect().width);
    const startX = event.clientX;
    let next = initial;
    const move = (pointerEvent) => {
      const delta = pointerEvent.clientX - startX;
      const left = Math.max(48, initial[index] + delta);
      const right = Math.max(48, initial[index + 1] - delta);
      const applied = left - initial[index];
      next = [...initial];
      next[index] = initial[index] + applied;
      next[index + 1] = initial[index + 1] - applied;
      if (right === 48) {
        next[index + 1] = 48;
        next[index] = initial[index] + initial[index + 1] - 48;
      }
      setColumnWidths(next);
    };
    const stop = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
      onChange({ ...table, headers, rows, headerHtml, cellHtml, columnWidths: next, rowHeights });
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop, { once: true });
  };
  const startRowResize = (event, index) => {
    const tableRows = [...(tableRef.current?.querySelectorAll('tr') || [])];
    if (!onChange || index >= tableRows.length - 1) return;
    event.preventDefault();
    event.stopPropagation();
    const initial = rowHeights.length === tableRows.length
      ? [...rowHeights]
      : tableRows.map((row) => row.getBoundingClientRect().height);
    const startY = event.clientY;
    let next = initial;
    const move = (pointerEvent) => {
      const delta = pointerEvent.clientY - startY;
      const top = Math.max(28, initial[index] + delta);
      const bottom = Math.max(28, initial[index + 1] - delta);
      const applied = top - initial[index];
      next = [...initial];
      next[index] = initial[index] + applied;
      next[index + 1] = initial[index + 1] - applied;
      if (bottom === 28) {
        next[index + 1] = 28;
        next[index] = initial[index] + initial[index + 1] - 28;
      }
      setRowHeights(next);
    };
    const stop = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', stop);
      onChange({ ...table, headers, rows, headerHtml, cellHtml, columnWidths, rowHeights: next });
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop, { once: true });
  };
  const updateHeaderHtml = (index, html) => {
    const nextHeaderHtml = [...headerHtml];
    nextHeaderHtml[index] = html;
    const nextHeaders = [...headers];
    nextHeaders[index] = plainTextFromHtml(html);
    onChange?.({ ...table, headers: nextHeaders, rows, headerHtml: nextHeaderHtml, cellHtml, headerStyles, cellStyles });
  };
  const updateCellHtml = (rowIndex, colIndex, html) => {
    const nextCellHtml = cellHtml.map((row) => Array.isArray(row) ? [...row] : []);
    while (nextCellHtml.length <= rowIndex) nextCellHtml.push([]);
    nextCellHtml[rowIndex][colIndex] = html;
    const nextRows = rows.map((row) => [...row]);
    while (nextRows[rowIndex].length < headers.length) nextRows[rowIndex].push('');
    nextRows[rowIndex][colIndex] = plainTextFromHtml(html);
    onChange?.({ ...table, headers, rows: nextRows, headerHtml, cellHtml: nextCellHtml, headerStyles, cellStyles });
  };
  const updateHeaderStyle = (index, patch) => {
    const next = headerStyles.map((style) => ({ ...(style || {}) }));
    const nextHeaderHtml = [...headerHtml];
    const nextCellHtml = cellHtml.map((row) => Array.isArray(row) ? [...row] : []);
    while (next.length < headers.length) next.push({});
    const nextCells = cellStyles.map((row) => Array.isArray(row) ? row.map((style) => ({ ...(style || {}) })) : []);
    for (let row = 0; row <= rows.length; row += 1) {
      for (let col = 0; col < headers.length; col += 1) {
        if (!(cellRange && isCellSelected(0, index)) || !isCellSelected(row, col)) continue;
        if (row === 0) {
          next[col] = { ...next[col], ...patch };
          nextHeaderHtml[col] = removeConflictingInlineStyles(nextHeaderHtml[col], patch);
        }
        else {
          while (nextCells.length < row) nextCells.push([]);
          while (nextCells[row - 1].length < headers.length) nextCells[row - 1].push({});
          nextCells[row - 1][col] = { ...nextCells[row - 1][col], ...patch };
          while (nextCellHtml.length < row) nextCellHtml.push([]);
          nextCellHtml[row - 1][col] = removeConflictingInlineStyles(nextCellHtml[row - 1][col], patch);
        }
      }
    }
    if (!(cellRange && isCellSelected(0, index))) {
      next[index] = { ...next[index], ...patch };
      nextHeaderHtml[index] = removeConflictingInlineStyles(nextHeaderHtml[index], patch);
    }
    onChange?.({ ...table, headers, rows, headerHtml: nextHeaderHtml, cellHtml: nextCellHtml, headerStyles: next, cellStyles: nextCells });
  };
  const updateCellStyle = (rowIndex, colIndex, patch) => {
    const next = cellStyles.map((row) => Array.isArray(row) ? row.map((style) => ({ ...(style || {}) })) : []);
    const nextHeaderHtml = [...headerHtml];
    const nextCellHtml = cellHtml.map((row) => Array.isArray(row) ? [...row] : []);
    while (next.length <= rowIndex) next.push([]);
    while (next[rowIndex].length < headers.length) next[rowIndex].push({});
    const nextHeaders = headerStyles.map((style) => ({ ...(style || {}) }));
    while (nextHeaders.length < headers.length) nextHeaders.push({});
    for (let row = 0; row <= rows.length; row += 1) {
      for (let col = 0; col < headers.length; col += 1) {
        if (!(cellRange && isCellSelected(rowIndex + 1, colIndex)) || !isCellSelected(row, col)) continue;
        if (row === 0) {
          nextHeaders[col] = { ...nextHeaders[col], ...patch };
          nextHeaderHtml[col] = removeConflictingInlineStyles(nextHeaderHtml[col], patch);
        }
        else {
          while (next.length < row) next.push([]);
          while (next[row - 1].length < headers.length) next[row - 1].push({});
          next[row - 1][col] = { ...next[row - 1][col], ...patch };
          while (nextCellHtml.length < row) nextCellHtml.push([]);
          nextCellHtml[row - 1][col] = removeConflictingInlineStyles(nextCellHtml[row - 1][col], patch);
        }
      }
    }
    if (!(cellRange && isCellSelected(rowIndex + 1, colIndex))) {
      next[rowIndex][colIndex] = { ...next[rowIndex][colIndex], ...patch };
      while (nextCellHtml.length <= rowIndex) nextCellHtml.push([]);
      nextCellHtml[rowIndex][colIndex] = removeConflictingInlineStyles(nextCellHtml[rowIndex][colIndex], patch);
    }
    onChange?.({ ...table, headers, rows, headerHtml: nextHeaderHtml, cellHtml: nextCellHtml, headerStyles: nextHeaders, cellStyles: next });
  };
  const addRow = () => {
    onChange?.({
      ...table, headers, rows: [...rows, headers.map(() => '')], headerHtml,
      cellHtml: [...cellHtml, []], headerStyles, cellStyles: [...cellStyles, []], rowHeights: [],
    });
  };
  const removeRow = () => {
    if (!rows.length) return;
    onChange?.({
      ...table, headers, rows: rows.slice(0, -1), headerHtml,
      cellHtml: cellHtml.slice(0, -1), headerStyles, cellStyles: cellStyles.slice(0, -1), rowHeights: [],
    });
  };
  const addColumn = () => {
    const nextHeaders = [...headers, `Cột ${headers.length + 1}`];
    const nextRows = rows.map((row) => [...row, '']);
    onChange?.({
      ...table, headers: nextHeaders, rows: nextRows, headerHtml: [...headerHtml, ''], cellHtml,
      headerStyles: [...headerStyles, {}],
      cellStyles: cellStyles.map((row) => [...(Array.isArray(row) ? row : []), {}]),
      columnWidths: [],
    });
  };
  const removeColumn = () => {
    if (headers.length <= 1) return;
    const nextHeaders = headers.slice(0, -1);
    const nextRows = rows.map((row) => row.slice(0, nextHeaders.length));
    onChange?.({
      ...table,
      headers: nextHeaders,
      rows: nextRows,
      headerHtml: headerHtml.slice(0, nextHeaders.length),
      cellHtml: cellHtml.map((row) => Array.isArray(row) ? row.slice(0, nextHeaders.length) : []),
      headerStyles: headerStyles.slice(0, nextHeaders.length),
      cellStyles: cellStyles.map((row) => Array.isArray(row) ? row.slice(0, nextHeaders.length) : []),
      columnWidths: [],
    });
  };
  if (!headers.length) return <div className="sv-empty">Không có dữ liệu bảng</div>;

  return (
    <div className="sv-table-wrap" style={{ borderColor: theme.surfaceBorder, '--table-font-size': `${tableFontSize}px` }}
      onPaste={pasteCellMatrix}
      onPointerDown={(event) => {
        if (event.target.closest('.sv-cell-editor, .sv-column-resizer, .sv-row-resizer')) {
          event.stopPropagation();
          onInteract?.();
        }
      }}>
      {onChange && (
        <DraggableActions>
          <span>{visibleRows.length}/{rows.length}</span>
          <i className="sv-action-kind"><Rows3 size={12} /><span>Hàng</span></i>
          <button type="button" onClick={addRow} title="Thêm hàng" aria-label="Thêm hàng"><Plus size={12} /></button>
          <button type="button" onClick={removeRow} disabled={!rows.length} title="Xóa hàng cuối" aria-label="Xóa hàng cuối"><Minus size={12} /></button>
          <i className="sv-action-separator" />
          <i className="sv-action-kind"><Columns3 size={12} /><span>Cột</span></i>
          <button type="button" onClick={addColumn} title="Thêm cột" aria-label="Thêm cột"><Plus size={12} /></button>
          <button type="button" onClick={removeColumn} disabled={headers.length <= 1} title="Xóa cột cuối" aria-label="Xóa cột cuối"><Minus size={12} /></button>
        </DraggableActions>
      )}
      <table ref={tableRef} className="sv-table" style={tableGridStyle}>
        <colgroup>
          {headers.map((_, index) => (
            <col key={index} style={{ width: columnWidths[index] ? `${columnWidths[index]}px` : `${100 / headers.length}%` }} />
          ))}
        </colgroup>
        <thead>
          <tr>{headers.map((header, index) => (
            <th key={index} className="sv-editable-cell"
              style={{ color: theme.text, background: theme.primary + '20' }}>
              <TableCellEditor value={header} html={headerHtml[index]} editable={Boolean(onChange)}
                onPointerDown={(event) => beginCellSelection(event, 0, index)}
                onPointerEnter={() => extendCellSelection(0, index)}
                rangeSelected={isCellSelected(0, index)}
                batchMode={rangeCellCount > 1 && isCellSelected(0, index)}
                baseFontSize={tableFontSize}
                elementKey={`table-header-${index}`} onSave={(html) => updateHeaderHtml(index, html)}
                style={headerStyles[index] || {}} onStyleChange={(patch) => updateHeaderStyle(index, patch)} />
              {onChange && index < headers.length - 1 && (
                <button type="button" className="sv-column-resizer" onPointerDown={(event) => startColumnResize(event, index)}
                  title="Kéo để đổi độ rộng cột" aria-label={`Đổi độ rộng cột ${index + 1}`} />
              )}
              {onChange && index === 0 && visibleRows.length > 0 && (
                <button type="button" className="sv-row-resizer" onPointerDown={(event) => startRowResize(event, 0)}
                  title="Kéo để đổi chiều cao hàng" aria-label="Đổi chiều cao hàng tiêu đề" />
              )}
            </th>
          ))}</tr>
        </thead>
        <tbody>
          {visibleRows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {headers.map((_, colIndex) => (
                <td key={colIndex} className="sv-editable-cell" style={{ borderColor: theme.surfaceBorder }}>
                  <TableCellEditor value={row[colIndex]} html={cellHtml[rowIndex]?.[colIndex]}
                    onPointerDown={(event) => beginCellSelection(event, rowIndex + 1, colIndex)}
                    onPointerEnter={() => extendCellSelection(rowIndex + 1, colIndex)}
                    rangeSelected={isCellSelected(rowIndex + 1, colIndex)}
                    batchMode={rangeCellCount > 1 && isCellSelected(rowIndex + 1, colIndex)}
                    baseFontSize={tableFontSize}
                    editable={Boolean(onChange)} elementKey={`table-cell-${rowIndex}-${colIndex}`}
                    onSave={(html) => updateCellHtml(rowIndex, colIndex, html)}
                    style={cellStyles[rowIndex]?.[colIndex] || {}}
                    onStyleChange={(patch) => updateCellStyle(rowIndex, colIndex, patch)} />
                  {onChange && colIndex === 0 && rowIndex < visibleRows.length - 1 && (
                    <button type="button" className="sv-row-resizer" onPointerDown={(event) => startRowResize(event, rowIndex + 1)}
                      title="Kéo để đổi chiều cao hàng" aria-label={`Đổi chiều cao hàng ${rowIndex + 1}`} />
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function chartData(chart) {
  const labels = chart?.labels || chart?.categories || [];
  const rawSeries = Array.isArray(chart?.series) && chart.series.length
    ? chart.series
    : [{ name: chart?.title || 'Giá trị', values: chart?.values || [] }];
  const series = rawSeries.map((item, index) => ({
    ...(item && typeof item === 'object' ? item : {}),
    name: item?.name || `Dữ liệu ${index + 1}`,
    values: (item?.values || item?.data || []).map((value) => Number(value) || 0),
  }));
  return { labels: labels.map(String), series };
}

export function ChartVisual({ chart, theme, onChange }) {
  const [editingData, setEditingData] = useState(false);
  const { labels, series } = chartData(chart);
  const rawType = String(chart?.chart_type || chart?.type || 'bar').toLowerCase();
  const type = rawType === 'column' ? 'bar' : rawType === 'donut' ? 'doughnut' : rawType;
  const selectorType = type === 'line_smooth'
    ? 'line'
    : type === 'area_stacked'
      ? 'area'
      : ['column_stacked', 'column_stacked_100'].includes(type)
        ? 'bar'
        : ['bar_stacked', 'bar_stacked_100'].includes(type)
          ? 'bar_horizontal'
          : type;
  const allValues = series.flatMap((item) => item.values);
  const unit = chart?.unit ? ` ${chart.unit}` : '';
  const labelChars = labels.reduce((sum, label) => sum + String(label).length, 0);
  const chartFontSize = labels.length > 8 || labelChars > 130 ? 8 : labels.length > 6 || labelChars > 90 ? 9 : 11;
  const saveChart = (nextLabels, nextSeries) => {
    const nextChart = { ...chart, series: nextSeries };
    if (Array.isArray(chart?.categories) && !Array.isArray(chart?.labels)) {
      nextChart.categories = nextLabels;
    } else {
      nextChart.labels = nextLabels;
    }
    onChange?.(nextChart);
  };
  const updateLabel = (index, value) => {
    const nextLabels = [...labels];
    nextLabels[index] = value;
    saveChart(nextLabels, series);
  };
  const updateValue = (seriesIndex, valueIndex, value) => {
    const parsed = Number(String(value).replace(',', '.'));
    if (!Number.isFinite(parsed)) return;
    const nextSeries = series.map((item) => ({ ...item, values: [...item.values] }));
    nextSeries[seriesIndex].values[valueIndex] = parsed;
    if (Array.isArray(nextSeries[seriesIndex].data)) {
      nextSeries[seriesIndex].data = [...nextSeries[seriesIndex].values];
    }
    saveChart(labels, nextSeries);
  };
  const updateSeriesName = (seriesIndex, value) => {
    const nextSeries = series.map((item) => ({ ...item, values: [...item.values] }));
    nextSeries[seriesIndex].name = value;
    saveChart(labels, nextSeries);
  };
  const addCategory = () => {
    const nextLabels = [...labels, `Mục ${labels.length + 1}`];
    const nextSeries = series.map((item) => {
      const next = { ...item, values: [...item.values, 0] };
      if (Array.isArray(next.data)) next.data = [...next.values];
      return next;
    });
    saveChart(nextLabels, nextSeries);
  };
  const removeCategory = () => {
    if (!labels.length) return;
    const nextSeries = series.map((item) => {
      const next = { ...item, values: item.values.slice(0, -1) };
      if (Array.isArray(next.data)) next.data = [...next.values];
      return next;
    });
    saveChart(labels.slice(0, -1), nextSeries);
  };
  const changeChartType = (nextType) => {
    onChange?.({ ...chart, type: nextType, chart_type: nextType });
  };
  const chartRows = labels.map((label, labelIndex) => {
    const row = { label };
    series.forEach((item, seriesIndex) => {
      row[`series_${seriesIndex}`] = item.values[labelIndex] ?? 0;
    });
    return row;
  });
  const toolbar = onChange && (
    <DraggableActions>
      <select value={selectorType} onChange={(event) => changeChartType(event.target.value)} aria-label="Loại biểu đồ">
        <option value="bar">Cột</option>
        <option value="line">Đường</option>
        <option value="area">Miền</option>
        <option value="pie">Tròn</option>
        <option value="doughnut">Donut</option>
        <option value="bar_horizontal">Thanh ngang</option>
        <option value="radar">Radar</option>
      </select>
      <button type="button" className={`sv-action-text ${editingData ? 'active' : ''}`} onClick={() => setEditingData((value) => !value)} title="Chỉnh dữ liệu" aria-label="Chỉnh dữ liệu"><Pencil size={12} /><span>Dữ liệu</span></button>
      <i className="sv-action-separator" />
      <button type="button" onClick={addCategory} title="Thêm mục dữ liệu" aria-label="Thêm mục dữ liệu"><Plus size={12} /></button>
      <button type="button" onClick={removeCategory} disabled={labels.length <= 1} title="Xóa mục cuối" aria-label="Xóa mục cuối"><Minus size={12} /></button>
    </DraggableActions>
  );
  const dataEditor = onChange && editingData && (
    <div className="sv-chart-data-editor">
      <table>
        <thead>
          <tr>
            <th>Nhãn</th>
            {series.map((item, seriesIndex) => (
              <th key={seriesIndex} contentEditable suppressContentEditableWarning
                onBlur={(event) => updateSeriesName(seriesIndex, event.currentTarget.innerText.trim())}>{item.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((label, labelIndex) => (
            <tr key={`${label}-${labelIndex}`}>
              <td contentEditable suppressContentEditableWarning
                onBlur={(event) => updateLabel(labelIndex, event.currentTarget.innerText.trim())}>{label}</td>
              {series.map((item, seriesIndex) => (
                <td key={seriesIndex} contentEditable suppressContentEditableWarning
                  onBlur={(event) => updateValue(seriesIndex, labelIndex, event.currentTarget.innerText.trim())}>
                  {item.values[labelIndex] ?? 0}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  if (!labels.length || !allValues.length) return <div className="sv-empty">Không có dữ liệu biểu đồ</div>;

  if (type === 'pie' || type === 'donut' || type === 'doughnut') {
    const values = series[0].values.slice(0, labels.length);
    const rawTotal = values.reduce((sum, value) => sum + Math.max(0, value), 0);
    const total = rawTotal || 1;
    const percentages = values.map((value) => Math.max(0, value) / total * 100);
    const stops = percentages.map((percentage, index) => {
      const start = percentages.slice(0, index).reduce((sum, value) => sum + value, 0);
      return `${COLORS[index % COLORS.length]} ${start}% ${start + percentage}%`;
    }).join(', ');
    return (
      <div className="sv-pie-layout">
        {toolbar}
        {dataEditor}
        <div className="sv-pie-wrap">
          <div className="sv-pie" style={{ background: rawTotal ? `conic-gradient(${stops})` : theme.surface }} />
          {type === 'doughnut' && (
            <div className="sv-pie-center" style={{ background: theme.bg, color: theme.text }}>
              <strong>{rawTotal}</strong>
              <span style={{ color: theme.textSub }}>Tổng</span>
            </div>
          )}
        </div>
        <div className="sv-legend">{labels.map((label, i) => (
          <div key={`${label}-${i}`} className={(values[i] ?? 0) === 0 ? 'is-zero' : ''}>
            <i style={{ background: COLORS[i % COLORS.length] }} />
            <span className="sv-editable-value" contentEditable={Boolean(onChange)} suppressContentEditableWarning
              onBlur={(event) => updateLabel(i, event.currentTarget.innerText.trim())}>{label}</span>
            <strong className="sv-editable-value" contentEditable={Boolean(onChange)} suppressContentEditableWarning
              onBlur={(event) => updateValue(0, i, event.currentTarget.innerText.replace(unit, '').trim())}>{values[i] ?? 0}{unit}</strong>
            <small>{Math.round(percentages[i] || 0)}%</small>
          </div>
        ))}</div>
      </div>
    );
  }

  const axisColor = theme.textSub || '#94a3b8';
  const gridColor = theme.surfaceBorder || 'rgba(148,163,184,.2)';
  const tooltipStyle = {
    background: theme.bg,
    border: `1px solid ${gridColor}`,
    borderRadius: 6,
    color: theme.text,
    fontSize: 11,
  };
  const common = (
    <>
      <CartesianGrid stroke={gridColor} strokeDasharray="3 4" vertical={false} />
      <XAxis dataKey="label" tick={{ fill: axisColor, fontSize: chartFontSize }} axisLine={{ stroke: gridColor }} tickLine={false} />
      <YAxis tick={{ fill: axisColor, fontSize: 9 }} axisLine={false} tickLine={false} width={38} />
      <Tooltip contentStyle={tooltipStyle} />
      {series.length > 1 && <Legend wrapperStyle={{ color: axisColor, fontSize: 10 }} />}
    </>
  );
  let chartNode;
  if (type === 'line' || type === 'line_smooth') {
    chartNode = (
      <LineChart data={chartRows} margin={{ top: 28, right: 18, bottom: 4, left: 0 }}>
        {common}
        {series.map((item, index) => (
          <Line key={index} type={type === 'line_smooth' ? 'monotone' : 'linear'} dataKey={`series_${index}`}
            name={item.name} stroke={COLORS[index % COLORS.length]} strokeWidth={3} dot={{ r: 3 }} activeDot={{ r: 5 }} />
        ))}
      </LineChart>
    );
  } else if (type === 'area' || type === 'area_stacked') {
    chartNode = (
      <AreaChart data={chartRows} margin={{ top: 28, right: 18, bottom: 4, left: 0 }}>
        {common}
        {series.map((item, index) => (
          <Area key={index} type="monotone" dataKey={`series_${index}`} name={item.name}
            stackId={type === 'area_stacked' ? 'stack' : undefined}
            stroke={COLORS[index % COLORS.length]} fill={COLORS[index % COLORS.length]} fillOpacity={0.24} strokeWidth={2.5} />
        ))}
      </AreaChart>
    );
  } else if (type === 'radar') {
    chartNode = (
      <RadarChart data={chartRows} margin={{ top: 20, right: 36, bottom: 18, left: 36 }}>
        <PolarGrid stroke={gridColor} />
        <PolarAngleAxis dataKey="label" tick={{ fill: axisColor, fontSize: chartFontSize }} />
        <PolarRadiusAxis tick={{ fill: axisColor, fontSize: 8 }} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        {series.map((item, index) => (
          <Radar key={index} dataKey={`series_${index}`} name={item.name}
            stroke={COLORS[index % COLORS.length]} fill={COLORS[index % COLORS.length]} fillOpacity={0.2} strokeWidth={2.5} />
        ))}
        {series.length > 1 && <Legend wrapperStyle={{ color: axisColor, fontSize: 10 }} />}
      </RadarChart>
    );
  } else {
    const horizontal = ['bar_horizontal', 'bar_stacked', 'bar_stacked_100'].includes(type);
    const stacked = ['column_stacked', 'column_stacked_100', 'bar_stacked', 'bar_stacked_100'].includes(type);
    const percentStack = ['column_stacked_100', 'bar_stacked_100'].includes(type);
    chartNode = (
      <BarChart data={chartRows} layout={horizontal ? 'vertical' : 'horizontal'} stackOffset={percentStack ? 'expand' : 'none'}
        margin={{ top: 28, right: 18, bottom: 4, left: horizontal ? 30 : 0 }}>
        <CartesianGrid stroke={gridColor} strokeDasharray="3 4" horizontal={!horizontal} vertical={horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" tick={{ fill: axisColor, fontSize: 9 }} axisLine={{ stroke: gridColor }} tickLine={false} />
            <YAxis type="category" dataKey="label" tick={{ fill: axisColor, fontSize: chartFontSize }} axisLine={false} tickLine={false} width={70} />
          </>
        ) : (
          <>
            <XAxis dataKey="label" tick={{ fill: axisColor, fontSize: chartFontSize }} axisLine={{ stroke: gridColor }} tickLine={false} />
            <YAxis tick={{ fill: axisColor, fontSize: 9 }} axisLine={false} tickLine={false} width={38} />
          </>
        )}
        <Tooltip contentStyle={tooltipStyle} />
        {series.length > 1 && <Legend wrapperStyle={{ color: axisColor, fontSize: 10 }} />}
        {series.map((item, index) => (
          <Bar key={index} dataKey={`series_${index}`} name={item.name}
            stackId={stacked ? 'stack' : undefined} fill={COLORS[index % COLORS.length]} radius={stacked ? 0 : [4, 4, 0, 0]} />
        ))}
      </BarChart>
    );
  }

  return (
    <div className="sv-chart" style={{ '--chart-font-size': `${chartFontSize}px` }}>
      {toolbar}
      {dataEditor}
      <div className="sv-recharts">
        <ResponsiveContainer width="100%" height="100%">{chartNode}</ResponsiveContainer>
      </div>
    </div>
  );
}
