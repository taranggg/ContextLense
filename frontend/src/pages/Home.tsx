import { DocumentList } from "../components/DocumentList";
import { Uploader } from "../components/Uploader";
import { Notice } from "../components/common";
import { useDocuments } from "../lib/hooks";
import { useReady } from "../lib/readiness";
import { Button } from "@/components/ui/button";

export function Home() {
  const { documents, error, refresh } = useDocuments();
  const { readiness } = useReady();
  const maxMb = readiness?.limits.max_upload_mb ?? 25;
  const maxFiles = readiness?.limits.max_files_per_upload ?? 5;

  return (
    <main className="mx-auto max-w-[1080px] px-6 pb-24 pt-[72px]">
      <section>
        <h1 className="max-w-[18ch] text-[clamp(36px,6vw,56px)] font-semibold leading-[1.07] tracking-[-0.03em]">
          A clearer way to explore your documents.
        </h1>
        <p className="mt-5 max-w-[54ch] text-[19px] leading-[1.5] text-muted-foreground">
          Upload PDFs — up to {maxFiles} at a time — and ask questions about them. Every answer points to the passages it
          came from, and everything runs on this machine.
        </p>
      </section>

      <Uploader maxMb={maxMb} maxFiles={maxFiles} onChange={refresh} />

      <section className="mt-[72px]" aria-labelledby="docs-title">
        <div className="mb-4 flex items-baseline justify-between gap-4">
          <h2 id="docs-title" className="text-xl font-semibold">
            Documents
          </h2>
        </div>
        {error && !documents ? (
          <Notice tone="error" actions={<Button variant="secondary" size="sm" onClick={refresh}>Try again</Button>}>
            {error.message}
          </Notice>
        ) : documents ? (
          <DocumentList documents={documents} onChange={refresh} />
        ) : (
          <p className="py-10 text-center text-[15px] text-muted-foreground">Loading…</p>
        )}
      </section>
    </main>
  );
}
