import { Link } from "react-router-dom";
import { CANVAS_REGISTRY } from "@/lib/canvas/canvas-registry";

/**
 * /architecture — landing page that lists the bundled canvas pages.
 * Operators land here from the top-nav and pick which architecture view
 * they want to spelunk.
 */
export function ArchitectureIndexRoute() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">Architecture canvases</h1>
        <p className="text-sm text-muted-foreground">
          Visual references for the GuardPipeline. Each canvas supports the <strong>Spread</strong>{" "}
          button (auto-layout) and pan / zoom; the new-flow canvas can replay any rid&apos;s
          executed path stage-by-stage.
        </p>
      </header>

      <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {CANVAS_REGISTRY.map((entry) => (
          <li key={entry.slug}>
            <Link
              to={`/architecture/${entry.slug}`}
              className="flex h-full flex-col gap-2 rounded-md border bg-card p-4 transition-colors hover:border-primary"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">{entry.title}</h2>
                {entry.ridDrivable ? (
                  <span className="rounded bg-primary/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
                    rid replay
                  </span>
                ) : null}
              </div>
              <p className="text-xs text-muted-foreground">{entry.description}</p>
              <span className="mt-auto text-[10px] text-muted-foreground">
                {entry.data.nodes.length} nodes · {entry.data.edges.length} edges
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
