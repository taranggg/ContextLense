import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { Header } from "./components/Header";
import { ReadinessProvider } from "./lib/readiness";
import { Home } from "./pages/Home";
import { Research } from "./pages/Research";
import { Workspace } from "./pages/Workspace";

function NotFound() {
  return (
    <main className="page page-narrow">
      <h1 style={{ fontSize: 28 }}>Page not found</h1>
      <p style={{ marginTop: 12 }}>
        <Link to="/">Back to documents</Link>
      </p>
    </main>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <ReadinessProvider>
        <Header />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/documents/:id" element={<Workspace />} />
          <Route path="/research" element={<Research />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </ReadinessProvider>
    </BrowserRouter>
  );
}
