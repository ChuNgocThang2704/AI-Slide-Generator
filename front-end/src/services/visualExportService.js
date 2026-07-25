import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';
import { projectService } from './documentService';

const sleep = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

async function waitForExportAssets(container, timeoutMs = 20000) {
  await document.fonts?.ready;

  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const images = Array.from(container?.querySelectorAll('img') || []);
    const pending = images.filter((image) => !image.complete || image.naturalWidth <= 0 || image.naturalHeight <= 0);
    if (!pending.length) return;
    await sleep(150);
  }

  const failed = Array.from(container?.querySelectorAll('img') || [])
    .filter((image) => !image.complete || image.naturalWidth <= 0 || image.naturalHeight <= 0);
  throw new Error(`Khong the tai day du ${failed.length} anh de xuat file.`);
}

const blobToDataUrl = (blob) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result);
  reader.onerror = () => reject(reader.error);
  reader.readAsDataURL(blob);
});

async function inlineExportImages(container, projectId) {
  if (!projectId) return () => {};
  const images = Array.from(container?.querySelectorAll('img') || []);
  const originals = images.map((image) => image.getAttribute('src') || '');
  const resolvedSources = images.map((image) => image.currentSrc || image.src || '');

  await Promise.all(images.map(async (image, index) => {
    const source = resolvedSources[index];
    if (!source || source.startsWith('data:') || source.startsWith('blob:')) return;
    const blob = await projectService.getProjectImage(projectId, source);
    image.src = await blobToDataUrl(blob);
  }));

  return () => {
    images.forEach((image, index) => {
      image.src = originals[index];
    });
  };
}

export async function captureSlides(container, { projectId } = {}) {
  const elements = Array.from(container?.querySelectorAll('[data-export-slide]') || []);
  if (!elements.length) throw new Error('Khong tim thay slide de xuat');

  let restoreImages = () => {};
  try {
    restoreImages = await inlineExportImages(container, projectId);
    await waitForExportAssets(container);

    const snapshots = [];
    for (let index = 0; index < elements.length; index += 1) {
      const canvas = await html2canvas(elements[index], {
        backgroundColor: null,
        scale: 2,
        useCORS: true,
        allowTaint: false,
        imageTimeout: 15000,
        logging: false,
        width: 960,
        height: 540,
        windowWidth: 960,
        windowHeight: 540,
      });
      try {
        snapshots.push(canvas.toDataURL('image/png', 1));
      } catch {
        throw new Error(`Khong the dong goi anh o slide ${index + 1}`);
      }
    }
    return snapshots;
  } finally {
    restoreImages();
  }
}

export async function exportSnapshotsToPdf(snapshots, fileName = 'presentation') {
  if (!snapshots.length) throw new Error('Khong co slide de xuat PDF');
  const pdf = new jsPDF({ orientation: 'landscape', unit: 'px', format: [960, 540], hotfixes: ['px_scaling'] });

  snapshots.forEach((snapshot, index) => {
    if (index > 0) pdf.addPage([960, 540], 'landscape');
    pdf.addImage(snapshot, 'PNG', 0, 0, 960, 540, undefined, 'FAST');
  });

  const safeName = String(fileName || 'presentation').replace(/[\\/:*?"<>|]+/g, '').replace(/\s+/g, '_').slice(0, 80) || 'presentation';
  pdf.save(`${safeName}.pdf`);
}
