import { DocumentList } from "../components/DocumentList";
import { Uploader } from "../components/Uploader";
import { Notice } from "../components/common";
import { useDocuments } from "../lib/hooks";
import { useReady } from "../lib/readiness";

export function Home() {
  const { documents, error, refresh } = useDocuments();
  const { readiness } = useReady();
  const maxMb = readiness?.limits.max_upload_mb ?? 25;

  return (
    <main className="page">
      <section className="hero">
        <h1>A clearer way to explore your documents.</h1>
        <p>
          Upload a PDF and ask questions about it. Every answer points to the passages it came from, and everything runs on
          this machine.
        </p>
      </section>

      <Uploader maxMb={maxMb} onChange={refresh} />

      <section className="section" aria-labelledby="docs-title">
        <div className="section-head">
          <h2 id="docs-title" className="section-title">
            Documents
          </h2>
        </div>
        {error && !documents ? (
          <Notice tone="error" actions={<button className="btn btn-secondary btn-sm" onClick={refresh}>Try again</button>}>
            {error.message}
          </Notice>
        ) : documents ? (
          <DocumentList documents={documents} onChange={refresh} />
        ) : (
          <p className="empty">Loading…</p>
        )}
      </section>
    </main>
  );
}
