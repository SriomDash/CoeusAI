import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { uploadPdf, runIngestion } from "./services/api";

function Sparkles({ count = 14 }) {
  const items = useMemo(() => {
    const arr = [];
    for (let i = 0; i < count; i++) {
      arr.push({
        id: i,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: 4 + Math.random() * 10,
        delay: Math.random() * 2.2,
        dur: 1.8 + Math.random() * 1.8,
        alpha: 0.22 + Math.random() * 0.35,
      });
    }
    return arr;
  }, [count]);

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      {items.map((s) => (
        <motion.span
          key={s.id}
          className="absolute rounded-full"
          style={{
            left: `${s.x}%`,
            top: `${s.y}%`,
            width: s.size,
            height: s.size,
            opacity: s.alpha,
          }}
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: [0.6, 1.05, 0.7], opacity: [0, s.alpha, 0] }}
          transition={{
            duration: s.dur,
            delay: s.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
      <style>{`
        .rounded-full { background: radial-gradient(circle, rgba(59,130,246,.9) 0%, rgba(59,130,246,.18) 55%, rgba(59,130,246,0) 70%); }
      `}</style>
    </div>
  );
}

export default function UploadPage() {
  const navigate = useNavigate();

  const userName = useMemo(() => localStorage.getItem("coeus_name") || "User", []);
  const userId = useMemo(() => localStorage.getItem("coeus_user_id"), []);

  const [file, setFile] = useState(null);

  // stages: idle -> uploading -> uploaded -> ingesting -> done
  const [stage, setStage] = useState("idle");

  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);

  const [jobId, setJobId] = useState(localStorage.getItem("coeus_job_id") || "");
  const [uploadedName, setUploadedName] = useState(localStorage.getItem("coeus_pdf_name") || "");

  const setPdfFile = (f) => {
    setError("");
    if (!f) return;
    if (f.type !== "application/pdf") {
      setFile(null);
      setError("Please select a PDF file only.");
      return;
    }
    setFile(f);
  };

  const onFileChange = (e) => setPdfFile(e.target.files?.[0]);

  const onUpload = async () => {
    if (!file) return setError("Please select a PDF first.");
    if (!userId) return setError("Session expired. Please restart from home.");

    setStage("uploading");
    setError("");

    try {
      // fetch-based api returns JSON directly
      const res = await uploadPdf(file, userId, userName);

      // Expecting: { status: "uploaded", job_id, filename }
      const jid = res.job_id; // ✅ no .data
      const fname = res.filename || file.name;

      if (!jid) throw new Error("Upload succeeded but job_id was missing from response.");

      setJobId(jid);
      setUploadedName(fname);

      localStorage.setItem("coeus_job_id", jid);
      localStorage.setItem("coeus_pdf_name", fname);

      setStage("uploaded");
    } catch (err) {
      setStage("idle");
      setError(err?.message || "Failed to upload. Check your server.");
    }
  };

  const onRunIngestion = async () => {
    if (!jobId) return setError("Missing job_id. Please upload again.");
    if (!userId) return setError("Session expired. Please restart from home.");

    setStage("ingesting");
    setError("");

    try {
      const res = await runIngestion(jobId, userId, userName);

      // Expecting: { status: "success", job_id, vectors_stored, docs_indexed }
      const vectors = res.vectors_stored ?? 0; // ✅ no .data
      const docs = res.docs_indexed ?? 0;

      localStorage.setItem("coeus_vectors_stored", String(vectors));
      localStorage.setItem("coeus_docs_indexed", String(docs));

      setStage("done");

      // Go to chat once ingestion is finished
      navigate("/chat");
    } catch (err) {
      setStage("uploaded"); // allow retry
      setError(err?.message || "Ingestion failed.");
    }
  };

  // Drag & Drop logic
  const onDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };
  const onDragLeave = () => setDragging(false);
  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    setPdfFile(e.dataTransfer.files?.[0]);
  };

  const uploading = stage === "uploading";
  const uploaded = stage === "uploaded" || stage === "ingesting" || stage === "done";
  const ingesting = stage === "ingesting";

  return (
    <div className="min-h-screen bg-[#f4f7fa] text-[#1e293b] px-6 py-10 overflow-hidden relative">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 -left-32 h-[420px] w-[420px] rounded-full bg-white blur-3xl opacity-80" />
        <div className="absolute top-1/3 -right-40 h-[520px] w-[520px] rounded-full bg-white blur-3xl opacity-80" />
        <div className="absolute bottom-[-220px] left-1/3 h-[560px] w-[560px] rounded-full bg-white blur-3xl opacity-70" />
      </div>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="relative mx-auto max-w-3xl">
        <motion.div className="rounded-[24px] border border-[#e2e8f0] bg-white p-8 shadow-sm relative overflow-hidden">
          <Sparkles />
          <div className="text-xs font-bold uppercase tracking-widest text-blue-600">Upload</div>

          <h1 className="mt-3 text-3xl font-extrabold tracking-tight">
            Hey <span className="text-blue-600">{userName}</span>, upload your PDF
          </h1>

          <p className="mt-3 text-[#64748b]">
            Upload first, then click <span className="font-semibold">Run ingestion</span>.
          </p>

          <motion.div
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            className={`mt-8 rounded-[16px] border border-dashed p-6 relative transition-all ${
              dragging ? "border-blue-600 bg-blue-50/50 ring-2 ring-blue-600/20" : "border-[#cbd5e1] bg-[#f8fafc]"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <label className="block text-sm font-semibold mb-1">Select a PDF</label>
                <div className="text-xs text-[#64748b]">Drag & drop your PDF into this box.</div>
              </div>
              <div className="rounded-full border border-[#e2e8f0] bg-white px-3 py-1 text-xs font-bold text-blue-600">PDF</div>
            </div>

            <input
              type="file"
              accept="application/pdf"
              disabled={uploading || uploaded} // lock input after upload
              onChange={onFileChange}
              className="mt-4 block w-full text-sm text-[#64748b] file:mr-4 file:rounded-[10px] file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:text-white file:font-semibold hover:file:bg-blue-700 disabled:opacity-50"
            />

            <AnimatePresence>
              {file && !error && stage === "idle" && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 text-sm font-medium text-blue-700">
                  Ready to upload: {file.name}
                </motion.div>
              )}

              {uploaded && !error && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 text-sm font-medium text-green-700">
                  Uploaded ✅ {uploadedName}
                </motion.div>
              )}

              {error && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 text-sm text-red-600">
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Upload button */}
            <motion.button
              onClick={onUpload}
              disabled={!file || uploading || uploaded}
              className={`mt-6 w-full rounded-[12px] px-5 py-3 font-semibold transition-all ${
                file && !uploading && !uploaded
                  ? "bg-blue-600 text-white hover:shadow-lg"
                  : "bg-[#e2e8f0] text-[#64748b] cursor-not-allowed"
              }`}
            >
              {uploading ? "Uploading..." : uploaded ? "Uploaded" : "Upload PDF"}
            </motion.button>

            {/* Ingestion trigger button */}
            <motion.button
              onClick={onRunIngestion}
              disabled={!uploaded || ingesting}
              className={`mt-3 w-full rounded-[12px] px-5 py-3 font-semibold transition-all ${
                uploaded && !ingesting
                  ? "bg-[#0f172a] text-white hover:shadow-lg"
                  : "bg-[#e2e8f0] text-[#64748b] cursor-not-allowed"
              }`}
            >
              {ingesting ? "Running ingestion..." : "Run ingestion →"}
            </motion.button>

            {(uploading || ingesting) && (
              <div className="mt-4">
                <div className="h-1.5 w-full rounded-full bg-[#e2e8f0] overflow-hidden">
                  <motion.div
                    className="h-full bg-blue-600"
                    animate={{ x: ["-100%", "200%"] }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                    style={{ width: "40%" }}
                  />
                </div>
                <div className="mt-2 text-xs text-[#64748b]">
                  {uploading ? "Saving your file…" : "Indexing and storing vectors…"}
                </div>
              </div>
            )}

            {/* Reset */}
            {uploaded && !ingesting && (
              <button
                onClick={() => {
                  setStage("idle");
                  setFile(null);
                  setJobId("");
                  setUploadedName("");
                  localStorage.removeItem("coeus_job_id");
                  localStorage.removeItem("coeus_pdf_name");
                  setError("");
                }}
                className="mt-3 w-full rounded-[12px] px-5 py-3 font-semibold text-[#64748b] hover:bg-[#f1f5f9]"
              >
                Upload a different PDF
              </button>
            )}

            <button
              onClick={() => navigate("/")}
              className="mt-3 w-full rounded-[12px] px-5 py-3 font-semibold text-[#64748b] hover:bg-[#f1f5f9]"
            >
              ← Back
            </button>
          </motion.div>
        </motion.div>
      </motion.div>
    </div>
  );
}