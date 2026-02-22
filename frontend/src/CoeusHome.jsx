import React, { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { registerUser } from "./services/api"; // Path to your api.js

const COEUS_SRC = "/coeus.png";

function clampName(s) {
  return s.replace(/\s+/g, " ").trim().slice(0, 24);
}

function Sparkles({ count = 16 }) {
  const sparkles = useMemo(() => {
    const arr = [];
    for (let i = 0; i < count; i++) {
      arr.push({
        id: i,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: 4 + Math.random() * 10,
        delay: Math.random() * 2.2,
        dur: 1.8 + Math.random() * 1.8,
        alpha: 0.25 + Math.random() * 0.45,
      });
    }
    return arr;
  }, [count]);

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      {sparkles.map((s) => (
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
          animate={{ scale: [0.6, 1.1, 0.7], opacity: [0, s.alpha, 0] }}
          transition={{
            duration: s.dur,
            delay: s.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
      <style>{`
        .rounded-full { background: radial-gradient(circle, rgba(59,130,246,.9) 0%, rgba(59,130,246,.2) 55%, rgba(59,130,246,0) 70%); }
      `}</style>
    </div>
  );
}

export default function CoeusHome() {
  const [name, setName] = useState("");
  const [touched, setTouched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const cleanName = clampName(name);
  const canStart = cleanName.length >= 2;

  useEffect(() => {
    const saved = localStorage.getItem("coeus_name");
    if (saved) setName(saved);
  }, []);

  const handleStart = async () => {
    if (!canStart || loading) return;
    
    setTouched(true);
    setLoading(true);
    setError("");

    try {
      // 1. Register user in Supabase via FastAPI
      const response = await registerUser(cleanName);
      
      // 2. Persist details for the upload page
      localStorage.setItem("coeus_name", cleanName);
      localStorage.setItem("coeus_user_id", response.user.id); // The UUID from DB
      
      // 3. Navigate
      window.location.href = "/upload";
    } catch (err) {
      setError(err.message || "Server connection failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#f4f7fa] text-[#1e293b] overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 -left-32 h-[420px] w-[420px] rounded-full bg-white blur-3xl opacity-80" />
        <div className="absolute top-1/3 -right-40 h-[520px] w-[520px] rounded-full bg-white blur-3xl opacity-80" />
        <div className="absolute bottom-[-220px] left-1/3 h-[560px] w-[560px] rounded-full bg-white blur-3xl opacity-70" />
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-6xl items-center px-6 py-10">
        <div className="grid w-full grid-cols-1 gap-10 lg:grid-cols-2 lg:gap-14">
          <div className="flex flex-col justify-center">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="inline-flex items-center gap-2 self-start rounded-full border border-[#e2e8f0] bg-white px-4 py-2 shadow-sm"
            >
              <span className="h-2 w-2 rounded-full bg-[#ea4e59]" />
              <span className="text-sm font-semibold text-[#64748b]">
                Coeus • Chat with your PDFs
              </span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-6 text-4xl font-extrabold tracking-tight lg:text-5xl"
            >
              Turn PDFs into a conversation.
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-4 max-w-xl text-base leading-relaxed text-[#64748b]"
            >
              Upload any PDF and ask questions. Coeus finds the right parts and gives you clear answers—fast.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-8 rounded-[24px] border border-[#e2e8f0] bg-white p-6 shadow-sm"
            >
              <div className="mb-2 text-xs font-bold uppercase tracking-widest text-[#ea4e59]">
                Start here
              </div>

              <label className="block text-sm font-semibold text-[#1e293b]">
                What should Coeus call you?
              </label>

              <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="relative flex-1">
                  <input
                    value={name}
                    disabled={loading}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Enter your name"
                    className="w-full rounded-[10px] border bg-[#f8fafc] px-4 py-3 text-base outline-none focus:border-[#ea4e59]"
                  />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[#64748b]">
                    {cleanName.length}/24
                  </div>
                </div>

                <motion.button
                  whileHover={canStart && !loading ? { y: -1 } : {}}
                  whileTap={canStart && !loading ? { scale: 0.98 } : {}}
                  onClick={handleStart}
                  disabled={!canStart || loading}
                  className={[
                    "rounded-[10px] px-6 py-3 font-semibold transition-all",
                    canStart && !loading
                      ? "bg-[#ea4e59] text-white shadow hover:bg-[#d9444f]"
                      : "bg-[#e2e8f0] text-[#64748b] cursor-not-allowed",
                  ].join(" ")}
                >
                  {loading ? "Joining..." : "Start →"}
                </motion.button>
              </div>

              <AnimatePresence>
                {(touched && !canStart) || error ? (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className={`mt-3 text-sm ${error ? 'text-red-500' : 'text-[#64748b]'}`}
                  >
                    {error || "Please enter at least 2 characters."}
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </motion.div>
          </div>

          <div className="relative flex items-center justify-center">
            <div className="relative w-full max-w-md">
              <motion.div
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                className="relative rounded-[24px] border border-[#e2e8f0] bg-white p-6 shadow-sm overflow-hidden"
              >
                <Sparkles count={18} />
                <div className="relative flex flex-col items-center justify-center">
                  <motion.img
                    src={COEUS_SRC}
                    alt="Coeus mascot"
                    className="select-none"
                    style={{ width: 220, height: "auto" }}
                    animate={{ y: [0, -10, 0], rotate: [-1, 1, -1] }}
                    transition={{ duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
                  />
                  <div className="mt-5 text-center">
                    <div className="text-sm font-bold text-[#1e293b]">“Drop a PDF, ask anything.”</div>
                    <div className="mt-1 text-xs text-[#64748b]">Coeus will guide you to the answer.</div>
                  </div>
                </div>
              </motion.div>
              <div className="mt-4 text-center text-xs text-[#64748b]">© {new Date().getFullYear()} Coeus</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}