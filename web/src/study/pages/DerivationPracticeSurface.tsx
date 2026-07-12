// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import katex from "katex";

type StepResponse = { expr?: string; expr_py?: string; justification?: string };

export function DerivationPracticeSurface({
  steps,
  targetSteps,
  check,
  value,
  onChange,
}: {
  steps: Array<{ expr?: string; justification?: string; cloze?: boolean }>;
  targetSteps?: Array<{ expr?: string; justification?: string }>;
  check?: "normalized-match" | "numeric-equivalence";
  value: Record<string, StepResponse>;
  onChange: (value: Record<string, StepResponse>) => void;
}) {
  const update = (index: number, patch: StepResponse) => onChange({
    ...value,
    [String(index)]: { ...value[String(index)], ...patch },
  });
  return <ol className="kq-study-derivation">{steps.map((step, index) => {
    const response = value[String(index)] ?? {};
    const reference = targetSteps?.[index];
    return <li key={index}>
      {step.cloze ? <>
        {reference?.expr || reference?.justification ? <div className="kq-study-derivation-target">
          {reference.expr ? <MathLine value={reference.expr} /> : null}
          {reference.justification ? <p>{reference.justification}</p> : null}
        </div> : null}
        <textarea value={response.expr ?? ""} onChange={(event) => update(index, { expr: event.currentTarget.value })} placeholder="补上这一步" aria-label={`Derivation step ${index + 1}`} />
        {check === "numeric-equivalence" ? <input value={response.expr_py ?? ""} onChange={(event) => update(index, { expr_py: event.currentTarget.value })} placeholder="可选：机器可检表达式" aria-label={`Machine expression ${index + 1}`} /> : null}
        <input value={response.justification ?? ""} onChange={(event) => update(index, { justification: event.currentTarget.value })} placeholder="为什么成立" aria-label={`Justification ${index + 1}`} />
      </> : <><MathLine value={step.expr ?? ""} />{step.justification ? <p>{step.justification}</p> : null}</>}
    </li>;
  })}</ol>;
}

function MathLine({ value }: { value: string }) {
  return <div className="kq-study-math-line" dangerouslySetInnerHTML={{ __html: katex.renderToString(value, { throwOnError: false }) }} />;
}
