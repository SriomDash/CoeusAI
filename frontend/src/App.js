import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import CoeusHome from "./CoeusHome";
import UploadPage from "./UploadPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CoeusHome />} />
        <Route path="/upload" element={<UploadPage />} />
      </Routes>
    </BrowserRouter>
  );
}