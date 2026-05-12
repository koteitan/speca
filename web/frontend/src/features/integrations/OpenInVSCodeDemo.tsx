// Dev-only demo for <OpenInVSCode>.
//
// Not wired into routes.tsx (that's Slice G's job — they own the route
// table for the settings / dev area). To eyeball the variants locally:
//
//   // App.tsx — TEMPORARY
//   import { OpenInVSCodeDemo } from "@/features/integrations/OpenInVSCodeDemo";
//   ...
//   <OpenInVSCodeDemo />
//
// Remove the import before commit (or let Slice G fold it into the dev
// route table). The component is self-contained: it does not own routing,
// query providers, or layout — those come from `main.tsx` / `App.tsx`.

import type { ReactElement, ReactNode } from "react";

import { OpenInVSCode } from "@/components/OpenInVSCode";
import { useIntegrationsStatus } from "./useIntegrationsStatus";

// Pin the demo to absolute paths the developer is likely to have locally.
// The "disabled" demo simulates a missing-CLI state by passing a clearly
// bogus path — the button is still enabled but the click will surface
// the failure path through the mutation toast.
const DEMO_REPO = "C:\\Users\\shieru_k\\Documents\\speca";
const DEMO_FILE = "C:\\Users\\shieru_k\\Documents\\speca\\web\\server\\main.py";

export function OpenInVSCodeDemo(): ReactElement {
  const status = useIntegrationsStatus();
  return (
    <section
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--nyx-space-6)",
        padding: "var(--nyx-space-7)",
        maxWidth: 720,
      }}
    >
      <header>
        <h2 style={{ margin: 0 }}>OpenInVSCode demo</h2>
        <p style={{ marginTop: "var(--nyx-space-2)", color: "#555" }}>
          status: {status.isLoading ? "loading" : JSON.stringify(status.data)}
        </p>
      </header>

      <Row title="folder (button)">
        <OpenInVSCode path={DEMO_REPO} label="VSCode で repo を開く" />
      </Row>

      <Row title="file (button)">
        <OpenInVSCode path={DEMO_FILE} label="VSCode で main.py を開く" />
      </Row>

      <Row title="file + line (button)">
        <OpenInVSCode
          path={DEMO_FILE}
          line={1}
          label="main.py L1 へジャンプ"
        />
      </Row>

      <Row title="icon-only">
        <OpenInVSCode
          path={DEMO_FILE}
          line={1}
          variant="icon"
          label="VSCode で開く"
        />
      </Row>

      <Row title="menuitem">
        <OpenInVSCode
          path={DEMO_FILE}
          line={1}
          variant="menuitem"
          label="VSCode でこの行を開く"
        />
      </Row>

      <Row title="installed (live status)">
        <span>
          code.installed = {String(status.data?.code.installed ?? "loading")}
          {" / "}gh.installed = {String(status.data?.gh.installed ?? "loading")}
          {" / "}gh.authed = {String(status.data?.gh.authed ?? "loading")}
        </span>
      </Row>
    </section>
  );
}

function Row({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}): ReactElement {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--nyx-space-6)",
        borderTop: "1px solid var(--nyx-color-border-muted)",
        paddingTop: "var(--nyx-space-4)",
      }}
    >
      <strong style={{ minWidth: 200 }}>{title}</strong>
      <div>{children}</div>
    </div>
  );
}
