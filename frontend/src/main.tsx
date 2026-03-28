import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./index.css";
import App from "./App";
import Overview from "./pages/Overview";
import Traces from "./pages/Traces";
import Metrics from "./pages/Metrics";
import Logs from "./pages/Logs";
import Chain from "./pages/Chain";
import Infra from "./pages/Infra";
import Docs from "./pages/Docs";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<Overview />} />
          <Route path="traces" element={<Traces />} />
          <Route path="metrics" element={<Metrics />} />
          <Route path="logs" element={<Logs />} />
          <Route path="chain" element={<Chain />} />
          <Route path="infra" element={<Infra />} />
          <Route path="docs" element={<Docs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>
);
