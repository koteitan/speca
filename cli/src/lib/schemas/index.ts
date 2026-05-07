/**
 * Schema validation layer.
 *
 * Wraps Ajv (with ajv-formats) and exposes typed validators for the JSON
 * artefacts the CLI writes — `TARGET_INFO.json` and `BUG_BOUNTY_SCOPE.json`.
 *
 * The schemas live under `./generated/` and are produced by
 * `npm run sync-schemas` from the repo-root `schemas/` directory (which is in
 * turn produced by `scripts/export_schemas.py`, U2 in the CLI roadmap).
 *
 * The `Input` types are also generated (`./generated/types.ts`) so renaming a
 * field in the Pydantic model surfaces as a compile error here, not a silent
 * runtime drift.
 */
import Ajv, { type ErrorObject, type ValidateFunction } from "ajv";
import addFormats from "ajv-formats";

import targetInfoSchema from "./generated/TargetInfo.schema.json" with { type: "json" };
import bugBountyScopeSchema from "./generated/BugBountyScopeInfo.schema.json" with { type: "json" };
import type { TargetInfo, BugBountyScopeInfo } from "./generated/types.js";

/**
 * `TargetInfoInput` / `BugBountyScopeInput` are kept as named aliases so
 * existing imports continue to work; the actual shape comes from the
 * generated types.
 */
export type TargetInfoInput = TargetInfo;
export type BugBountyScopeInput = BugBountyScopeInfo;

export type ValidationResult<T> =
  | { ok: true; data: T }
  | { ok: false; errors: ValidationError[] };

export interface ValidationError {
  path: string;
  message: string;
}

function buildValidator<T>(schema: object): ValidateFunction<T> {
  // Strip our `_generated` provenance bookkeeping so Ajv does not complain
  // about the unknown root key in strict mode.
  const cleaned: Record<string, unknown> = { ...(schema as Record<string, unknown>) };
  delete cleaned._generated;

  const ajv = new Ajv({
    allErrors: true,
    strict: false,
    useDefaults: true,
  });
  addFormats(ajv);
  return ajv.compile<T>(cleaned);
}

const targetInfoValidate = buildValidator<TargetInfoInput>(targetInfoSchema as object);
const bugBountyScopeValidate = buildValidator<BugBountyScopeInput>(bugBountyScopeSchema as object);

function toErrors(errors: ErrorObject[] | null | undefined): ValidationError[] {
  if (!errors) return [];
  return errors.map((e) => ({
    path: e.instancePath || "/",
    message: `${e.message ?? "invalid"}${e.params ? ` (${JSON.stringify(e.params)})` : ""}`,
  }));
}

export function validateTargetInfo(data: unknown): ValidationResult<TargetInfoInput> {
  const ok = targetInfoValidate(data);
  if (ok) {
    return { ok: true, data: data as TargetInfoInput };
  }
  return { ok: false, errors: toErrors(targetInfoValidate.errors) };
}

export function validateBugBountyScope(data: unknown): ValidationResult<BugBountyScopeInput> {
  const ok = bugBountyScopeValidate(data);
  if (ok) {
    return { ok: true, data: data as BugBountyScopeInput };
  }
  return { ok: false, errors: toErrors(bugBountyScopeValidate.errors) };
}

export function formatErrors(errors: ValidationError[]): string {
  return errors.map((e) => `  ${e.path}: ${e.message}`).join("\n");
}
