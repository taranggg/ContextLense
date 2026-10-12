import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { Header } from "./components/Header";
import { ReadinessProvider } from "./lib/readiness";
import { Home } from "./pages/Home";
import { Research } from "./pages/Research";
import { Workspace } from "./pages/Workspace";

function NotFound() {
  return (
    <main className="mx-auto max-w-[760px] px-6 pb-24 pt-[72px]">
      <h1 className="text-[28px] font-semibold">Page not found</h1>
      <p className="mt-3">
        <Link to="/" className="text-primary hover:underline">
          Back to documents
        </Link>
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
