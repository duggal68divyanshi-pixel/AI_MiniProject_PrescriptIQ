import React, { useState } from "react";
import { Upload, X, ArrowLeft, ArrowRight, Trash2, Plus, FileText, Image as ImageIcon } from "lucide-react";

export function MultiPhotoUploadModal({ isOpen, onClose, onUpload }) {
  const [pages, setPages] = useState([]); // [{ id, file, previewUrl, pageNum }]

  if (!isOpen) return null;

  const handleFileSelect = (e) => {
    const selected = Array.from(e.target.files || []);
    if (!selected.length) return;

    const newPages = selected.map((file, idx) => ({
      id: Math.random().toString(36).substring(2, 9),
      file,
      previewUrl: URL.createObjectURL(file),
      pageNum: pages.length + idx + 1,
    }));

    setPages((prev) => {
      const updated = [...prev, ...newPages];
      return updated.map((p, i) => ({ ...p, pageNum: i + 1 }));
    });
  };

  const movePage = (index, direction) => {
    const targetIdx = index + direction;
    if (targetIdx < 0 || targetIdx >= pages.length) return;

    const updated = [...pages];
    const temp = updated[index];
    updated[index] = updated[targetIdx];
    updated[targetIdx] = temp;

    setPages(updated.map((p, i) => ({ ...p, pageNum: i + 1 })));
  };

  const removePage = (index) => {
    const updated = pages.filter((_, i) => i !== index);
    setPages(updated.map((p, i) => ({ ...p, pageNum: i + 1 })));
  };

  const handleSubmit = () => {
    if (!pages.length) return;
    const orderedFiles = pages.map((p) => p.file);
    onUpload(orderedFiles);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <ImageIcon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-100 text-lg">Upload Paper Photos (Multi-Page Batch)</h3>
              <p className="text-xs text-slate-400">Order your paper page photos sequentially before OCR processing</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {pages.length === 0 ? (
            <div className="border-2 border-dashed border-slate-700/80 rounded-2xl p-12 text-center hover:border-indigo-500/50 transition cursor-pointer bg-slate-950/40">
              <input
                type="file"
                multiple
                accept="image/png, image/jpeg, image/jpg, image/webp"
                onChange={handleFileSelect}
                className="hidden"
                id="multi-photo-input"
              />
              <label htmlFor="multi-photo-input" className="cursor-pointer block">
                <Upload className="w-12 h-12 text-indigo-400 mx-auto mb-4 animate-pulse" />
                <h4 className="text-slate-200 font-medium text-base mb-1">Select or drag photos of your research paper</h4>
                <p className="text-xs text-slate-400 mb-4">Supports JPG, PNG, WEBP — Select multiple page photos at once</p>
                <span className="inline-flex items-center px-4 py-2 text-xs font-medium text-indigo-300 bg-indigo-500/10 rounded-lg border border-indigo-500/20 hover:bg-indigo-500/20 transition">
                  Browse Paper Photos
                </span>
              </label>
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-medium text-slate-300">
                  {pages.length} {pages.length === 1 ? "Page Photo" : "Page Photos"} Selected
                </span>
                <label
                  htmlFor="add-more-photos"
                  className="cursor-pointer text-xs font-medium text-indigo-400 hover:text-indigo-300 flex items-center gap-1.5"
                >
                  <Plus className="w-4 h-4" /> Add More Pages
                  <input
                    type="file"
                    multiple
                    accept="image/png, image/jpeg, image/jpg, image/webp"
                    onChange={handleFileSelect}
                    className="hidden"
                    id="add-more-photos"
                  />
                </label>
              </div>

              {/* Grid of Pages */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {pages.map((p, idx) => (
                  <div
                    key={p.id}
                    className="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-col justify-between group hover:border-indigo-500/40 transition shadow-md"
                  >
                    <div className="relative rounded-lg overflow-hidden bg-slate-900 mb-2 aspect-[3/4] border border-slate-800/80">
                      <img
                        src={p.previewUrl}
                        alt={`Page ${p.pageNum}`}
                        className="w-full h-full object-cover"
                      />
                      <span className="absolute top-2 left-2 bg-slate-900/90 backdrop-blur-md border border-slate-700 text-indigo-400 text-[10px] font-bold px-2 py-0.5 rounded-full">
                        Page {p.pageNum}
                      </span>
                    </div>

                    <div className="flex items-center justify-between pt-1 text-slate-400 text-xs">
                      <span className="truncate max-w-[100px] text-[11px]">{p.file.name}</span>
                      <div className="flex items-center gap-1">
                        <button
                          disabled={idx === 0}
                          onClick={() => movePage(idx, -1)}
                          className="p-1 hover:text-slate-200 hover:bg-slate-800 rounded disabled:opacity-30 transition"
                          title="Move Left"
                        >
                          <ArrowLeft className="w-3.5 h-3.5" />
                        </button>
                        <button
                          disabled={idx === pages.length - 1}
                          onClick={() => movePage(idx, 1)}
                          className="p-1 hover:text-slate-200 hover:bg-slate-800 rounded disabled:opacity-30 transition"
                          title="Move Right"
                        >
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => removePage(idx)}
                          className="p-1 text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 rounded transition"
                          title="Remove Page"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 transition"
          >
            Cancel
          </button>
          <button
            disabled={pages.length === 0}
            onClick={handleSubmit}
            className="px-5 py-2 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-2 shadow-lg shadow-indigo-600/20"
          >
            <FileText className="w-4 h-4" />
            Process & Run OCR ({pages.length} {pages.length === 1 ? "Page" : "Pages"})
          </button>
        </div>
      </div>
    </div>
  );
}
