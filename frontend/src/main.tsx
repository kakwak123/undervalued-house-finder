import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import DebugPage from "./pages/DebugPage";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/debug" element={<DebugPage />} />
        <Route
          path="*"
          element={
            <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400">
              <div className="text-center">
                <p className="text-xl font-mono">Undervalued House Finder</p>
                <a
                  href="/debug"
                  className="mt-4 block text-blue-400 underline hover:text-blue-300"
                >
                  Open Debug Dashboard
                </a>
              </div>
            </div>
          }
        />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
