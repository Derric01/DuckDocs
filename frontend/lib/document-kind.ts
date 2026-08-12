import {
  FileCode2,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileType2,
  type LucideIcon,
} from 'lucide-react';

/**
 * Document-kind index, shared by every surface that shows a file icon
 * (library rows, evidence panel, citation cards). Colour here is data, not
 * decoration: the same hue always means the same kind of file, so it has to
 * come from one place rather than being redefined per component.
 */
export function kindFor(nameOrType: string): { icon: LucideIcon; mark: string } {
  const extension = (nameOrType.split('.').pop() ?? nameOrType).toUpperCase();
  if (extension === 'PDF') return { icon: FileType2, mark: 'border-kind-slide/30 bg-kind-slide/12 text-kind-slide' };
  if (['CSV', 'XLSX'].includes(extension)) {
    return { icon: FileSpreadsheet, mark: 'border-kind-sheet/30 bg-kind-sheet/12 text-kind-sheet' };
  }
  if (['PNG', 'JPG', 'JPEG', 'WEBP', 'TIFF', 'TIF', 'BMP'].includes(extension)) {
    return { icon: FileImage, mark: 'border-kind-image/30 bg-kind-image/12 text-kind-image' };
  }
  if (['TS', 'TSX', 'JS', 'JSX', 'PY', 'JSON', 'XML', 'YAML', 'YML', 'SQL', 'GO', 'RS'].includes(extension)) {
    return { icon: FileCode2, mark: 'border-kind-code/30 bg-kind-code/12 text-kind-code' };
  }
  if (['DOCX', 'PPTX'].includes(extension)) {
    return { icon: FileText, mark: 'border-kind-doc/30 bg-kind-doc/12 text-kind-doc' };
  }
  return { icon: FileText, mark: 'border-border bg-muted text-kind-text' };
}
