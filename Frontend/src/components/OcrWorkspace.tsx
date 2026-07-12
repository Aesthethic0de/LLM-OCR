import React, { useEffect, useState, useRef, type ChangeEvent, type DragEvent } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowDownToLineIcon, AlertTriangleIcon, CheckIcon, ClipboardIcon, FileSearchIcon, FileTextIcon, MoreHorizontalIcon, PanelLeftCloseIcon, PlusIcon, RefreshCcwIcon, ScanLineIcon, ShieldCheckIcon, Trash2Icon, UploadCloudIcon, XIcon, ZoomInIcon, ZoomOutIcon } from 'lucide-react';
type WorkspaceStage = 'upload' | 'processing' | 'review';
type ToastMessage = 'Copied extracted data' | 'Export prepared' | 'OCR reprocessed' | null;
type ExtractedField = {
  label: string;
  value: string;
  confidence: number | null;
};
type LineItem = {
  description: string;
  quantity: string;
  amount: string;
};
type OcrResult = {
  document_name: string;
  page_count: number;
  overall_confidence: number | null;
  fields: ExtractedField[];
  line_items: LineItem[];
  raw_text: string | null;
};
function formatConfidence(confidence: number | null): string {
  return confidence === null || confidence === undefined ? '—' : `${Math.round(confidence)}%`;
}
export function OcrWorkspace() {
  const [stage, setStage] = useState<WorkspaceStage>('upload');
  const [documentName, setDocumentName] = useState('');
  const [isDragActive, setIsDragActive] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [toast, setToast] = useState<ToastMessage>(null);
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isPdf, setIsPdf] = useState(false);
  const [result, setResult] = useState<OcrResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2200);
    return () => window.clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);
  async function processFile(file: File) {
    setDocumentName(file.name);
    setCurrentFile(file);
    setIsPdf(file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf'));
    setPreviewUrl((existing) => {
      if (existing) URL.revokeObjectURL(existing);
      return URL.createObjectURL(file);
    });
    setError(null);
    setStage('processing');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch('/api/ocr/process', {
        method: 'POST',
        body: formData
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail ?? `Request failed with status ${response.status}`);
      }
      const data: OcrResult = await response.json();
      setResult(data);
      setStage('review');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong while processing the document.');
      setStage('upload');
    }
  }
  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) processFile(file);
    event.target.value = '';
  }
  function handleDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file) processFile(file);
  }
  function handleReprocess() {
    if (currentFile) {
      processFile(currentFile);
      showToast('OCR reprocessed');
    }
  }
  function showToast(message: Exclude<ToastMessage, null>) {
    setToast(message);
  }
  function updateField(index: number, patch: Partial<ExtractedField>) {
    setResult((prev) => {
      if (!prev) return prev;
      const fields = prev.fields.map((field, i) => i === index ? {
        ...field,
        ...patch
      } : field);
      return {
        ...prev,
        fields
      };
    });
  }
  function addField() {
    setResult((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        fields: [...prev.fields, {
          label: '',
          value: '',
          confidence: null
        }]
      };
    });
  }
  function removeField(index: number) {
    setResult((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        fields: prev.fields.filter((_, i) => i !== index)
      };
    });
  }
  return <main className="min-h-screen w-full bg-[#f5f5f1] text-[#17211f]">
      <input ref={inputRef} className="sr-only" type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={handleFileChange} aria-label="Upload a document" />

      <header className="flex h-[68px] items-center justify-between border-b border-[#dce0d8] bg-[#fbfbf8] px-5 sm:px-8">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center bg-[#163b35] text-white">
            <ScanLineIcon size={20} strokeWidth={2.2} aria-hidden="true" />
          </div>
          <div>
            <p className="text-[15px] font-bold tracking-[-0.02em]">
              Paperwork
            </p>
            <p className="hidden text-xs text-[#66706d] sm:block">
              Intelligent document review
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs font-medium text-[#52615d]">
          <span className="hidden items-center gap-1.5 sm:flex">
            <ShieldCheckIcon size={15} className="text-[#247660]" aria-hidden="true" />
            Private processing
          </span>
          <span className="h-4 w-px bg-[#dce0d8]" />
          <span>v1.4</span>
        </div>
      </header>

      <AnimatePresence mode="wait">
        {stage === 'upload' && <motion.section key="upload" initial={{
        opacity: 0,
        y: 10
      }} animate={{
        opacity: 1,
        y: 0
      }} exit={{
        opacity: 0,
        y: -10
      }} className="mx-auto flex min-h-[calc(100vh-68px)] max-w-6xl flex-col justify-center px-5 py-12 sm:px-8" aria-labelledby="upload-title">
            <div className="grid gap-12 lg:grid-cols-[1.05fr_.95fr] lg:items-center">
              <div className="max-w-xl">
                <div className="mb-6 inline-flex items-center gap-2 border border-[#cbd7d1] bg-[#e8f0eb] px-3 py-1.5 text-xs font-bold uppercase tracking-[0.13em] text-[#2c6052]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#39826a]" />
                  OCR workspace
                </div>
                <h1 id="upload-title" className="text-4xl font-semibold leading-[1.05] tracking-[-0.055em] text-[#17211f] sm:text-6xl">
                  Make every field
                  <br />
                  searchable.
                </h1>
                <p className="mt-6 max-w-md text-base leading-7 text-[#596561] sm:text-lg">
                  Drop in an invoice, statement, or form. We’ll structure the
                  details so you can verify them in one focused workspace.
                </p>
                <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-sm text-[#52615d]">
                  {['PDF, PNG, JPG', 'Up to 20 MB', 'Encrypted in transit'].map((item) => <span key={item} className="flex items-center gap-2">
                        <CheckIcon size={15} className="text-[#27725d]" aria-hidden="true" />
                        {item}
                      </span>)}
                </div>
                {error && <div className="mt-6 flex items-start gap-2.5 border border-[#e3b8ae] bg-[#fbeeeb] px-4 py-3 text-sm text-[#8a3a29]" role="alert">
                    <AlertTriangleIcon size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                    <span>{error}</span>
                  </div>}
              </div>

              <button type="button" onClick={() => inputRef.current?.click()} onDragEnter={(event) => {
            event.preventDefault();
            setIsDragActive(true);
          }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setIsDragActive(false)} onDrop={handleDrop} className={`group relative flex min-h-[380px] w-full flex-col items-center justify-center overflow-hidden border-2 border-dashed px-6 text-center transition-colors focus:outline-none focus:ring-4 focus:ring-[#9ec6b6] ${isDragActive ? 'border-[#247660] bg-[#e2eee8]' : 'border-[#b9c5bd] bg-[#fbfbf8] hover:border-[#247660]'}`} aria-label="Upload document by clicking or dropping a file">
                <div className="absolute left-0 top-0 h-1 w-full bg-[#d7e3dc]">
                  <div className={`h-full bg-[#357b65] transition-all duration-300 ${isDragActive ? 'w-full' : 'w-0 group-hover:w-1/3'}`} />
                </div>
                <div className="grid h-16 w-16 place-items-center rounded-full bg-[#e8f0eb] text-[#24634f]">
                  <UploadCloudIcon size={30} aria-hidden="true" />
                </div>
                <p className="mt-6 text-xl font-semibold tracking-[-0.03em]">
                  Drop your document here
                </p>
                <p className="mt-2 text-sm text-[#66706d]">
                  or click to browse from your computer
                </p>
                <span className="mt-8 border border-[#263f38] bg-[#173b34] px-5 py-3 text-sm font-semibold text-white transition-colors group-hover:bg-[#28554a]">
                  Select document
                </span>
                
              </button>
            </div>
          </motion.section>}

        {stage === 'processing' && <motion.section key="processing" initial={{
        opacity: 0
      }} animate={{
        opacity: 1
      }} exit={{
        opacity: 0
      }} className="flex min-h-[calc(100vh-68px)] items-center justify-center px-5" aria-live="polite">
            <div className="w-full max-w-sm text-center">
              <div className="relative mx-auto grid h-20 w-20 place-items-center border border-[#bbcdc3] bg-[#edf4ef] text-[#22624e]">
                <motion.div animate={{
              rotate: 360
            }} transition={{
              repeat: Infinity,
              duration: 1.8,
              ease: 'linear'
            }} className="absolute inset-1 border-2 border-transparent border-t-[#28765f]" />
                <FileSearchIcon size={28} aria-hidden="true" />
              </div>
              <h1 className="mt-7 text-2xl font-semibold tracking-[-0.035em]">
                Reading your document
              </h1>
              <p className="mt-3 text-sm leading-6 text-[#65716c]">
                {documentName}
              </p>
              <div className="mt-8 h-1.5 overflow-hidden bg-[#dce4de]">
                <motion.div className="h-full bg-[#327a64]" initial={{
              width: '8%'
            }} animate={{
              width: '92%'
            }} transition={{
              duration: 1.65,
              ease: 'easeInOut'
            }} />
              </div>
              <p className="mt-3 text-xs font-medium text-[#61716b]">
                Detecting fields and line items…
              </p>
            </div>
          </motion.section>}

        {stage === 'review' && result && <motion.section key="review" initial={{
        opacity: 0,
        y: 8
      }} animate={{
        opacity: 1,
        y: 0
      }} className="flex min-h-[calc(100vh-68px)] flex-col" aria-label="OCR document review">
            <div className="flex flex-col gap-4 border-b border-[#dce0d8] bg-[#fbfbf8] px-5 py-4 lg:flex-row lg:items-center lg:justify-between lg:px-8">
              <div className="flex min-w-0 items-center gap-3">
                <button type="button" onClick={() => setStage('upload')} className="grid h-9 w-9 shrink-0 place-items-center border border-[#d5ddd7] bg-white text-[#52615d] hover:text-[#173b34] focus:outline-none focus:ring-2 focus:ring-[#8cbaa9]" aria-label="Close document and upload another">
                  <XIcon size={17} />
                </button>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <FileTextIcon size={16} className="shrink-0 text-[#33775f]" aria-hidden="true" />
                    <h1 className="truncate text-sm font-bold tracking-[-0.015em]">
                      {documentName}
                    </h1>
                  </div>
                  <p className="mt-0.5 text-xs text-[#6a7571]">
                    {result.page_count} page{result.page_count === 1 ? '' : 's'} · processed just now
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="mr-1 inline-flex items-center gap-1.5 border border-[#bcd6c9] bg-[#eaf4ee] px-2.5 py-2 text-xs font-semibold text-[#287059]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#3d9576]" />
                  {formatConfidence(result.overall_confidence)} confidence
                </span>
                <ActionButton label="Copy data" icon={<ClipboardIcon size={15} />} onClick={() => {
              const text = result.fields.map((field) => `${field.label}: ${field.value}`).join('\n');
              navigator.clipboard.writeText(text).then(() => showToast('Copied extracted data'));
            }} />
                <ActionButton label="Export" icon={<ArrowDownToLineIcon size={15} />} onClick={() => {
              const blob = new Blob([JSON.stringify(result, null, 2)], {
                type: 'application/json'
              });
              const url = URL.createObjectURL(blob);
              const link = document.createElement('a');
              link.href = url;
              link.download = `${documentName.replace(/\.[^.]+$/, '')}.json`;
              link.click();
              URL.revokeObjectURL(url);
              showToast('Export prepared');
            }} />
                <button type="button" className="grid h-9 w-9 place-items-center border border-[#d4ddd7] bg-white text-[#52615d] hover:text-[#173b34] focus:outline-none focus:ring-2 focus:ring-[#8cbaa9]" aria-label="More document actions">
                  <MoreHorizontalIcon size={18} />
                </button>
              </div>
            </div>

            <div className="grid flex-1 lg:grid-cols-[minmax(0,1fr)_minmax(430px,.88fr)]">
              <section className="flex min-h-[530px] flex-col border-b border-[#dce0d8] bg-[#e9ece8] lg:border-b-0 lg:border-r" aria-labelledby="source-heading">
                <div className="flex h-12 shrink-0 items-center justify-between border-b border-[#d4dad5] bg-[#f5f6f3] px-4 sm:px-5">
                  <div className="flex items-center gap-2">
                    <PanelLeftCloseIcon size={15} className="text-[#66716c]" aria-hidden="true" />
                    <h2 id="source-heading" className="text-xs font-bold uppercase tracking-[0.1em] text-[#5d6863]">
                      Original document
                    </h2>
                  </div>
                  <div className="flex items-center gap-1">
                    <button type="button" onClick={() => setZoom((value) => Math.max(75, value - 10))} className="grid h-7 w-7 place-items-center text-[#56625d] hover:bg-[#e0e5e1] focus:outline-none focus:ring-2 focus:ring-[#8cbaa9]" aria-label="Zoom out">
                      <ZoomOutIcon size={15} />
                    </button>
                    <span className="w-10 text-center text-xs font-medium text-[#65716c]">
                      {zoom}%
                    </span>
                    <button type="button" onClick={() => setZoom((value) => Math.min(125, value + 10))} className="grid h-7 w-7 place-items-center text-[#56625d] hover:bg-[#e0e5e1] focus:outline-none focus:ring-2 focus:ring-[#8cbaa9]" aria-label="Zoom in">
                      <ZoomInIcon size={15} />
                    </button>
                  </div>
                </div>
                <div className="flex flex-1 items-start justify-center overflow-auto p-5 sm:p-8">
                  {previewUrl && (isPdf ? <embed src={previewUrl} type="application/pdf" className="h-[720px] w-full max-w-[700px] bg-[#fffefb] shadow-[0_14px_35px_rgba(35,49,42,.16)]" style={{
                transform: `scale(${zoom / 100})`,
                transformOrigin: 'top center'
              }} aria-label="Source document preview" /> : <img src={previewUrl} alt="Source document preview" className="w-full max-w-[600px] bg-[#fffefb] object-contain shadow-[0_14px_35px_rgba(35,49,42,.16)]" style={{
                transform: `scale(${zoom / 100})`,
                transformOrigin: 'top center'
              }} />)}
                </div>
              </section>

              <section className="bg-[#fbfbf8]" aria-labelledby="extraction-heading">
                <div className="flex h-12 items-center justify-between border-b border-[#dce0d8] px-5">
                  <div className="flex items-center gap-2">
                    <ScanLineIcon size={15} className="text-[#28745e]" aria-hidden="true" />
                    <h2 id="extraction-heading" className="text-xs font-bold uppercase tracking-[0.1em] text-[#53615c]">
                      Extracted data
                    </h2>
                  </div>
                  <span className="text-xs text-[#77827d]">
                    Click any value to edit
                  </span>
                </div>
                <div className="space-y-7 p-5 sm:p-7">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-lg font-semibold tracking-[-0.035em]">
                        Document details
                      </p>
                      <p className="mt-1 text-xs text-[#6b7672]">
                        {result.fields.length} field{result.fields.length === 1 ? '' : 's'} recognized automatically
                      </p>
                    </div>
                  </div>
                  {result.fields.length > 0 ? <dl className="divide-y divide-[#e1e5e1] border-y border-[#e1e5e1]">
                      {result.fields.map((field, index) => <div key={index} className="group grid grid-cols-[minmax(105px,.72fr)_1.25fr_auto_auto] items-center gap-3 py-2.5">
                          <dt>
                            <input type="text" value={field.label} onChange={(event) => updateField(index, {
                        label: event.target.value
                      })} placeholder="Field name" className="w-full border border-transparent bg-transparent px-1.5 py-1 text-xs text-[#6a7671] hover:border-[#dce2dd] focus:border-[#8cbaa9] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#8cbaa9]" />
                          </dt>
                          <dd>
                            <input type="text" value={field.value} onChange={(event) => updateField(index, {
                        value: event.target.value
                      })} placeholder="Value" className="w-full border border-transparent bg-transparent px-1.5 py-1 text-left text-sm font-semibold text-[#233c35] hover:border-[#dce2dd] focus:border-[#8cbaa9] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#8cbaa9]" />
                          </dd>
                          <span className="self-center text-[10px] font-bold text-[#3b896f]">
                            {formatConfidence(field.confidence)}
                          </span>
                          <button type="button" onClick={() => removeField(index)} className="grid h-6 w-6 place-items-center text-[#a4b0ab] opacity-0 transition-opacity hover:text-[#8a3a29] focus:outline-none focus:ring-2 focus:ring-[#8cbaa9] group-hover:opacity-100" aria-label={`Remove field ${field.label || index + 1}`}>
                            <Trash2Icon size={13} />
                          </button>
                        </div>)}
                    </dl> : <p className="border-y border-[#e1e5e1] py-4 text-xs text-[#6b7672]">
                      No fields were recognized in this document.
                    </p>}
                  <button type="button" onClick={addField} className="flex items-center gap-2 text-xs font-semibold text-[#33775f] hover:text-[#173b34] focus:outline-none focus:ring-2 focus:ring-[#8cbaa9]">
                    <PlusIcon size={14} /> Add field
                  </button>

                  {result.line_items.length > 0 && <div>
                      <div className="mb-3 flex items-end justify-between">
                        <div>
                          <h3 className="text-lg font-semibold tracking-[-0.035em]">
                            Line items
                          </h3>
                          <p className="mt-1 text-xs text-[#6b7672]">
                            {result.line_items.length} entr{result.line_items.length === 1 ? 'y' : 'ies'} detected
                          </p>
                        </div>
                      </div>
                      <div className="overflow-hidden border border-[#dce2dd]">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-[#f0f3ef] text-[10px] uppercase tracking-[0.08em] text-[#6f7c76]">
                            <tr>
                              <th className="px-3 py-2.5 font-bold">
                                Description
                              </th>
                              <th className="px-2 py-2.5 font-bold">Qty</th>
                              <th className="px-3 py-2.5 text-right font-bold">
                                Amount
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#e5e9e5] text-[#31453e]">
                            {result.line_items.map((item, index) => <tr key={`${item.description}-${index}`}>
                                <td className="max-w-[160px] px-3 py-3 font-medium leading-4">
                                  {item.description}
                                </td>
                                <td className="px-2 py-3 text-[#69756f]">
                                  {item.quantity}
                                </td>
                                <td className="whitespace-nowrap px-3 py-3 text-right font-semibold">
                                  {item.amount}
                                </td>
                              </tr>)}
                          </tbody>
                        </table>
                      </div>
                    </div>}

                  {result.raw_text && <div>
                      <div className="mb-3 flex items-end justify-between">
                        <div>
                          <h3 className="text-lg font-semibold tracking-[-0.035em]">
                            Raw text
                          </h3>
                          <p className="mt-1 text-xs text-[#6b7672]">
                            Full transcription of the document
                          </p>
                        </div>
                      </div>
                      <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words border border-[#dce2dd] bg-[#f5f6f3] px-3 py-2.5 text-xs leading-5 text-[#31453e]">
                        {result.raw_text}
                      </pre>
                    </div>}

                  <div className="border-l-2 border-[#4c927b] bg-[#eef5f0] px-4 py-3">
                    <p className="text-xs font-semibold text-[#225a49]">
                      Review complete
                    </p>
                    <p className="mt-1 text-xs leading-5 text-[#4d6960]">
                      Key fields are ready to export. Verify values against the
                      source document if needed.
                    </p>
                  </div>
                  <button type="button" onClick={handleReprocess} className="flex items-center gap-2 text-xs font-semibold text-[#64716c] hover:text-[#173b34] focus:outline-none focus:ring-2 focus:ring-[#8cbaa9]">
                    <RefreshCcwIcon size={14} /> Reprocess document
                  </button>
                </div>
              </section>
            </div>
          </motion.section>}
      </AnimatePresence>

      <AnimatePresence>
        {toast && <motion.div initial={{
        opacity: 0,
        y: 12
      }} animate={{
        opacity: 1,
        y: 0
      }} exit={{
        opacity: 0,
        y: 12
      }} className="fixed bottom-5 left-1/2 z-10 -translate-x-1/2 border border-[#b7d3c5] bg-[#173b34] px-4 py-3 text-sm font-medium text-white shadow-lg" role="status">
            <CheckIcon className="mr-2 inline-block text-[#8dd9b8]" size={16} />
            {toast}
          </motion.div>}
      </AnimatePresence>
    </main>;
}
type ActionButtonProps = {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
};
function ActionButton({
  label,
  icon,
  onClick
}: ActionButtonProps) {
  return <button type="button" onClick={onClick} className="inline-flex h-9 items-center gap-2 border border-[#d4ddd7] bg-white px-3 text-xs font-semibold text-[#3e504a] hover:border-[#9fbbb0] hover:text-[#173b34] focus:outline-none focus:ring-2 focus:ring-[#8cbaa9]">
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>;
}