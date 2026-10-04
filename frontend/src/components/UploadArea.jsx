import { useRef, useState } from "react";
import { uploadDocument, uploadPaperPhotosBatch } from "../services/api.js";
import { MultiPhotoUploadModal } from "./MultiPhotoUploadModal.jsx";
import { FileText, Camera, Upload } from "lucide-react";

export default function UploadArea({ onUploaded }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [showMultiPhotoModal, setShowMultiPhotoModal] = useState(false);

  async function handleFile(file) {
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const result = await uploadDocument(file);
      onUploaded(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleMultiPhotoUpload(files) {
    if (!files || !files.length) return;
    setError(null);
    setUploading(true);
    try {
      const result = await uploadPaperPhotosBatch(files);
      onUploaded(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const dropped = Array.from(e.dataTransfer.files || []);
          if (dropped.length > 1) {
            handleMultiPhotoUpload(dropped);
          } else {
            handleFile(dropped[0]);
          }
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-xl border border-dashed p-5 text-center transition-all ${
          dragOver ? "border-indigo-500 bg-indigo-500/10" : "border-slate-700 hover:border-slate-500 bg-slate-900/50"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf, image/png, image/jpeg, image/jpg, image/webp"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
        <div className="flex flex-col items-center justify-center">
          <Upload className="w-8 h-8 text-indigo-400 mb-2 animate-bounce" />
          <p className="font-mono text-xs font-semibold text-slate-200">
            {uploading ? "Processing & Running OCR…" : "Upload Research Paper or Photo"}
          </p>
          <p className="text-[11px] text-slate-400 mt-1">
            Supports PDF, Scanned PDF, JPG, PNG, WEBP
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between pt-1">
        <button
          type="button"
          onClick={() => setShowMultiPhotoModal(true)}
          className="w-full text-xs font-medium text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 px-3 py-2 rounded-xl transition flex items-center justify-center gap-2"
        >
          <Camera className="w-4 h-4" />
          Upload Paper Photos (Multi-Page Batch)
        </button>
      </div>

      {error && <p className="mt-2 text-xs text-rose-400 font-medium">{error}</p>}

      <MultiPhotoUploadModal
        isOpen={showMultiPhotoModal}
        onClose={() => setShowMultiPhotoModal(false)}
        onUpload={handleMultiPhotoUpload}
      />
    </div>
  );
}
