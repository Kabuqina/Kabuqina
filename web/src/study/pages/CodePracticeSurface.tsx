// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useRef } from "react";
import { EditorState } from "@codemirror/state";
import { Decoration, EditorView, keymap, lineNumbers, type ViewUpdate, ViewPlugin } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { defaultHighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { python } from "@codemirror/lang-python";

export function CodePracticeSurface({
  starter,
  targetCode,
  value,
  onChange,
}: {
  starter: string;
  targetCode?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const initialValue = useRef(value);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!root.current) return;
    const transcriptionDecorations = targetCode
      ? ViewPlugin.fromClass(class {
        decorations = Decoration.none;
        constructor(view: EditorView) {
          this.decorations = buildTranscriptionDecorations(view, targetCode!);
        }
        update(update: ViewUpdate) {
          if (update.docChanged) this.decorations = buildTranscriptionDecorations(update.view, targetCode!);
        }
      }, { decorations: (plugin) => plugin.decorations })
      : [];
    const state = EditorState.create({
      doc: initialValue.current || starter,
      extensions: [
        lineNumbers(),
        history(),
        keymap.of([...defaultKeymap, ...historyKeymap]),
        python(),
        syntaxHighlighting(defaultHighlightStyle),
        EditorView.lineWrapping,
        transcriptionDecorations,
        EditorView.updateListener.of((update) => {
          if (update.docChanged) onChangeRef.current(update.state.doc.toString());
        }),
      ],
    });
    const view = new EditorView({ state, parent: root.current });
    viewRef.current = view;
    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, [starter, targetCode]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const nextValue = value || starter;
    const currentValue = view.state.doc.toString();
    if (nextValue === currentValue) return;
    view.dispatch({ changes: { from: 0, to: currentValue.length, insert: nextValue } });
  }, [starter, value]);

  return (
    <div className="kq-study-code-practice">
      {targetCode ? <pre className="kq-study-code-target" aria-label="Transcription target">{targetCode}</pre> : null}
      <div ref={root} className="kq-study-code-editor" aria-label="Python code editor" />
    </div>
  );
}

export function transcriptionDiffRange(target: string, learner: string): { from: number; to: number } | null {
  const limit = 20_000;
  const safeTarget = target.slice(0, limit);
  const safeLearner = learner.slice(0, limit);
  let prefix = 0;
  while (prefix < safeTarget.length && prefix < safeLearner.length && safeTarget[prefix] === safeLearner[prefix]) prefix += 1;
  if (prefix === safeTarget.length && prefix === safeLearner.length) return null;

  let targetSuffix = safeTarget.length;
  let learnerSuffix = safeLearner.length;
  while (targetSuffix > prefix && learnerSuffix > prefix && safeTarget[targetSuffix - 1] === safeLearner[learnerSuffix - 1]) {
    targetSuffix -= 1;
    learnerSuffix -= 1;
  }
  return { from: prefix, to: learnerSuffix };
}

function buildTranscriptionDecorations(view: EditorView, targetCode: string) {
  const range = transcriptionDiffRange(targetCode, view.state.doc.toString());
  if (!range || range.from === range.to) return Decoration.none;
  return Decoration.set([Decoration.mark({ class: "kq-study-code-mismatch" }).range(range.from, range.to)]);
}
