import React, { useState, useEffect } from "react";
import { X, RefreshCw, Save, CheckCircle, AlertCircle, Eye, Cpu, FileEdit } from "lucide-react";
import { getDocumentPages, getDocumentPageImageUrl, reprocessPageOcr, updatePageText } from "../services/api";

export function OcrVerificationModal({ isOpen, onClose, documentId, documentTitle }) {
  const [pages, setPages] = useState([]);
  const [selectedPageNum, setSelectedPageNum] = useState(1);
  const [currentText, setCurrentText] = useState("");
  const [loading, setLoading] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [selectedEngine, setSelectedEngine] = useState("auto");

  useEffect(() => {
    if (isOpen && documentId) {
      loadPages();
    }
  }, [isOpen, documentId]);

  const loadPages = async () => {
    setLoading(true);
    try {
      const data = await getDocumentPages(documentId);
      setPages(data);
      if (data.length > 0) {
        const first = data[0];
        setSelectedPageNum(first.page_number);
        setCurrentText(first.extracted_text || "");
      }
    } catch (err) {
      console.error("Failed to load document pages:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const selectedPage = pages.find((p) => p.page_number === selectedPageNum) || pages[0];

  const handlePageSelect = (num) => {
    setSelectedPageNum(num);
    const p = pages.find((pg) => pg.page_number === num);
    if (p) {
      setCurrentText(p.extracted_text || "");
    }
  };

  const handleReprocess = async () => {
    if (!documentId || !selectedPageNum) return;
    setReprocessing(true);
    try {
      const res = await reprocessPageOcr(documentId, selectedPageNum, selectedEngine);
      setCurrentText(res.extracted_text);
      await loadPages();
    } catch (err) {
      alert(`OCR Reprocessing failed: ${err.message}`);
    } finally {
      setReprocessing(false);
    }
  };

  const handleSaveText = async () => {
    if (!documentId || !selectedPageNum) return;
    setSaving(true);
    try {
      await updatePageText(documentId, selectedPageNum, currentText);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
      await loadPages();
    } catch (err) {
      alert(`Failed to save text: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-6xl h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Eye className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-100 text-lg truncate max-w-xl">
                OCR Verification & Page Inspector
              </h3>
              <p className="text-xs text-slate-400 truncate max-w-xl">{documentTitle}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Page Selector Toolbar */}
        <div className="px-6 py-3 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between overflow-x-auto gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-400 mr-2">Pages:</span>
            {pages.map((p) => (
              <button
                key={p.page_number}
                onClick={() => handlePageSelect(p.page_number)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                  p.page_number === selectedPageNum
                    ? "bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/20"
                    : "bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700"
                }`}
              >
                Page {p.page_number} {p.user_edited && "✓"}
              </button>
            ))}
          </div>

          {selectedPage && (
            <div className="flex items-center gap-3 text-xs">
              <span className="px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                {selectedPage.ocr_engine || "Native"}
              </span>
              <span className="px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                {selectedPage.ocr_confidence_label}
              </span>
            </div>
          )}
        </div>

        {/* Split View Body */}
        <div className="flex-1 grid grid-cols-1 md:grid-cols-2 overflow-hidden divide-y md:divide-y-0 md:divide-x divide-slate-800">
          {/* Left Panel: Original Page Photo */}
          <div className="p-4 bg-slate-950 flex flex-col h-full overflow-hidden">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5" /> Original Page Image
              </span>
              <span className="text-[11px] text-slate-500">Page {selectedPageNum}</span>
            </div>
            <div className="flex-1 bg-slate-900 rounded-xl border border-slate-800 overflow-hidden flex items-center justify-center p-2 relative">
              {documentId && selectedPageNum ? (
                <img
                  src={getDocumentPageImageUrl(documentId, selectedPageNum)}
                  alt={`Original Page ${selectedPageNum}`}
                  className="max-h-full max-w-full object-contain rounded shadow-lg"
                  onError={(e) => {
                    e.target.style.display = 'none';
                    e.target.parentNode.innerHTML = '<div class="text-slate-500 text-xs text-center p-8">Original page image preview unavailable for native PDF pages</div>';
                  }}
                />
              ) : (
                <span className="text-xs text-slate-500">No image available</span>
              )}
            </div>
          </div>

          {/* Right Panel: Extracted OCR Text & Editor */}
          <div className="p-4 bg-slate-900 flex flex-col h-full overflow-hidden">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <FileEdit className="w-3.5 h-3.5 text-indigo-400" /> Extracted Text (Editable)
              </span>

              {/* Reprocess Controls */}
              <div className="flex items-center gap-2">
                <select
                  value={selectedEngine}
                  onChange={(e) => setSelectedEngine(e.target.value)}
                  className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-2 py-1 focus:outline-none focus:border-indigo-500"
                >
                  <option value="auto">Auto Engine</option>
                  <option value="tesseract">Tesseract OCR</option>
                  <option value="vision_llm">Vision LLM OCR</option>
                </select>
                <button
                  disabled={reprocessing}
                  onClick={handleReprocess}
                  className="px-2.5 py-1 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition flex items-center gap-1.5 disabled:opacity-50"
                  title="Re-run OCR on this page"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${reprocessing ? "animate-spin text-indigo-400" : ""}`} />
                  Reprocess
                </button>
              </div>
            </div>

            <textarea
              value={currentText}
              onChange={(e) => setCurrentText(e.target.value)}
              className="flex-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-slate-200 font-mono text-xs leading-relaxed focus:outline-none focus:border-indigo-500/80 resize-none"
              placeholder="OCR extracted text will appear here..."
            />

            <div className="mt-3 flex items-center justify-between">
              <span className="text-[11px] text-slate-500 font-mono">
                {currentText.length} characters
              </span>

              <div className="flex items-center gap-3">
                {saveSuccess && (
                  <span className="text-xs font-medium text-emerald-400 flex items-center gap-1 animate-fade-in">
                    <CheckCircle className="w-3.5 h-3.5" /> Text Verified & Saved
                  </span>
                )}
                <button
                  disabled={saving}
                  onClick={handleSaveText}
                  className="px-4 py-2 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition flex items-center gap-2 shadow-lg shadow-indigo-600/20 disabled:opacity-50"
                >
                  <Save className="w-4 h-4" /> Save Verified Text
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
