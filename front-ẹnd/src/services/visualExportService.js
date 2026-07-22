import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

export async function captureSlides(container) {
  const elements = Array.from(container?.querySelectorAll('[data-export-slide]') || []);
  if (!elements.length) throw new Error('Không tìm thấy slide để xuất');

  const snapshots = [];
  for (const element of elements) {
    const canvas = await html2canvas(element, {
      backgroundColor: null,
      scale: 2,
      useCORS: true,
      logging: false,
      width: 960,
      height: 540,
    });
    snapshots.push(canvas.toDataURL('image/png', 1));
  }
  return snapshots;
}

export async function exportSnapshotsToPdf(snapshots, fileName = 'presentation') {
  if (!snapshots.length) throw new Error('Không có slide để xuất PDF');
  const pdf = new jsPDF({ orientation: 'landscape', unit: 'px', format: [960, 540], hotfixes: ['px_scaling'] });

  snapshots.forEach((snapshot, index) => {
    if (index > 0) pdf.addPage([960, 540], 'landscape');
    pdf.addImage(snapshot, 'PNG', 0, 0, 960, 540, undefined, 'FAST');
  });

  const safeName = String(fileName || 'presentation').replace(/[\\/:*?"<>|]+/g, '').replace(/\s+/g, '_').slice(0, 80) || 'presentation';
  pdf.save(`${safeName}.pdf`);
}
