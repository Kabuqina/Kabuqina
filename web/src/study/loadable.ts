// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

export type Loadable<T> =
  | { status: "idle" }
  | { status: "loading"; previous?: T }
  | { status: "ready"; data: T }
  | { status: "error"; error: unknown; previous?: T };

export function loading<T>(previous?: T): Loadable<T> {
  return previous === undefined ? { status: "loading" } : { status: "loading", previous };
}

export class RequestCoordinator {
  private generation = 0;
  private controller?: AbortController;

  begin(): { generation: number; signal: AbortSignal } {
    this.controller?.abort();
    this.controller = new AbortController();
    this.generation += 1;
    return { generation: this.generation, signal: this.controller.signal };
  }

  isCurrent(generation: number): boolean {
    return generation === this.generation && !this.controller?.signal.aborted;
  }

  cancel(): void {
    this.controller?.abort();
    this.generation += 1;
  }
}
