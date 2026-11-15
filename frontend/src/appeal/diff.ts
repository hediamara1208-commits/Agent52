import type { SessionView } from "../model/sessionView";

/** Client-side equivalent of guide/tribunal/appeal.py::diff_sessions (Req. 30.3). */
export interface SessionDiff {
  verdict: { original: VerdictKey; appeal: VerdictKey; changed: boolean };
  hard_rules: { rule: string; original: RuleKey | null; appeal: RuleKey | null }[];
  soft_preferences: { preference: string; original: string | null; appeal: string | null }[];
  exhibits: { metric: string; assets: string[]; original: ExhibitKey; appeal: ExhibitKey }[];
}
export interface VerdictKey { verdict: string | null; max_weight: number | null }
export interface RuleKey { status: string; observed: number | null; limit: number | null }
export interface ExhibitKey { number: number; value: unknown }

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
const vkey = (v: SessionView): VerdictKey => ({ verdict: v.verdict?.verdict ?? null, max_weight: v.verdict?.max_weight ?? null });
const rkey = (r: SessionView["rule_results"][number] | undefined): RuleKey | null =>
  r ? { status: r.status, observed: r.observed ?? null, limit: r.limit ?? null } : null;

function prefs(v: SessionView): Map<string, string> {
  const list = ((v.ruling as unknown as { assessments?: { preference?: string; assessment?: string }[] } | null)?.assessments) ?? [];
  const m = new Map<string, string>();
  for (const p of list) if (p.preference) m.set(p.preference, p.assessment ?? "");
  return m;
}

export function diffSessions(a: SessionView, b: SessionView): SessionDiff {
  const ra = new Map(a.rule_results.map((r) => [r.rule, r]));
  const rb = new Map(b.rule_results.map((r) => [r.rule, r]));
  const hard_rules = [...new Set([...ra.keys(), ...rb.keys()])].sort()
    .map((rule) => ({ rule, original: rkey(ra.get(rule)), appeal: rkey(rb.get(rule)) }))
    .filter((r) => !same(r.original, r.appeal));

  const pa = prefs(a), pb = prefs(b);
  const soft_preferences = [...new Set([...pa.keys(), ...pb.keys()])].sort()
    .map((preference) => ({ preference, original: pa.get(preference) ?? null, appeal: pb.get(preference) ?? null }))
    .filter((p) => p.original !== p.appeal);

  const key = (e: SessionView["exhibits"][number]) => `${e.metric}|${[...(e.assets ?? [])].sort().join(",")}`;
  const ea = new Map(a.exhibits.map((e) => [key(e), e]));
  const eb = new Map(b.exhibits.map((e) => [key(e), e]));
  const exhibits = [...ea.keys()].filter((k) => eb.has(k)).sort()
    .filter((k) => !same(ea.get(k)!.value, eb.get(k)!.value))
    .map((k) => {
      const x = ea.get(k)!, y = eb.get(k)!;
      return {
        metric: x.metric, assets: [...(x.assets ?? [])].sort(),
        original: { number: x.number, value: x.value }, appeal: { number: y.number, value: y.value },
      };
    });

  const va = vkey(a), vb = vkey(b);
  return { verdict: { original: va, appeal: vb, changed: !same(va, vb) }, hard_rules, soft_preferences, exhibits };
}
