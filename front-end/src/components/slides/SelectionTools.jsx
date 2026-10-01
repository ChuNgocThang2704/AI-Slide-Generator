import {
  AlignHorizontalDistributeCenter, AlignHorizontalJustifyCenter, AlignHorizontalJustifyEnd, AlignHorizontalJustifyStart,
  AlignVerticalDistributeCenter, AlignVerticalJustifyCenter, AlignVerticalJustifyEnd, AlignVerticalJustifyStart,
  Group, Ungroup,
} from 'lucide-react';
import './SelectionTools.css';

const stop = (event) => event.stopPropagation();

const ALIGNS = [
  ['left', 'Căn trái', AlignHorizontalJustifyStart],
  ['center', 'Căn giữa ngang', AlignHorizontalJustifyCenter],
  ['right', 'Căn phải', AlignHorizontalJustifyEnd],
  ['top', 'Căn trên', AlignVerticalJustifyStart],
  ['middle', 'Căn giữa dọc', AlignVerticalJustifyCenter],
  ['bottom', 'Căn dưới', AlignVerticalJustifyEnd],
];

/** Alignment, distribution and grouping for the current selection. */
export default function SelectionTools({ count, canGroup, canUngroup, onAlign, onDistribute, onGroup, onUngroup }) {
  const target = count > 1 ? 'các phần tử đã chọn' : 'trang chiếu';
  return (
    <div className="selection-tools" onPointerDown={stop}>
      <div className="st-title">Căn chỉnh theo {target}</div>
      <div className="st-row">
        {ALIGNS.map(([mode, label, Icon]) => (
          <button key={mode} type="button" title={label} aria-label={label} onClick={() => onAlign(mode)}>
            <Icon size={16} />
          </button>
        ))}
      </div>
      <div className="st-title">Phân bố đều</div>
      <div className="st-row">
        <button type="button" title="Phân bố đều theo chiều ngang (cần ≥ 3 phần tử)" aria-label="Phân bố ngang" disabled={count < 3} onClick={() => onDistribute('h')}>
          <AlignHorizontalDistributeCenter size={16} />
        </button>
        <button type="button" title="Phân bố đều theo chiều dọc (cần ≥ 3 phần tử)" aria-label="Phân bố dọc" disabled={count < 3} onClick={() => onDistribute('v')}>
          <AlignVerticalDistributeCenter size={16} />
        </button>
      </div>
      <div className="st-title">Nhóm</div>
      <div className="st-row wide">
        <button type="button" disabled={!canGroup} onClick={onGroup} title="Gộp nhóm (Ctrl+G)"><Group size={15} /> Gộp nhóm</button>
        <button type="button" disabled={!canUngroup} onClick={onUngroup} title="Tách nhóm (Ctrl+Shift+G)"><Ungroup size={15} /> Tách nhóm</button>
      </div>
    </div>
  );
}
