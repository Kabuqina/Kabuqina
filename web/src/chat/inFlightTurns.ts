import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { InFlightTurn } from "./inFlightTurnUtils";
export type { InFlightStatus, InFlightTurn } from "./inFlightTurnUtils";

export type InFlightTurnsController = {
  getTurn: (sessionId: string) => InFlightTurn | null;
  upsertTurn: (
    sessionId: string,
    next: InFlightTurn | ((prev: InFlightTurn | null) => InFlightTurn | null),
  ) => void;
  clearTurn: (sessionId: string) => void;
};

export function useInFlightTurns(): InFlightTurnsController {
  const [turns, setTurns] = useState<Record<string, InFlightTurn>>({});
  const turnsRef = useRef(turns);

  useEffect(() => {
    turnsRef.current = turns;
  }, [turns]);

  const getTurn = useCallback((sessionId: string) => turnsRef.current[sessionId] ?? null, []);

  const upsertTurn = useCallback<InFlightTurnsController["upsertTurn"]>((sessionId, next) => {
    setTurns((prev) => {
      const prevTurn = prev[sessionId] ?? null;
      const nextTurn = typeof next === "function" ? next(prevTurn) : next;
      if (!nextTurn) {
        const { [sessionId]: _removed, ...rest } = prev;
        return rest;
      }
      return { ...prev, [sessionId]: nextTurn };
    });
  }, []);

  const clearTurn = useCallback((sessionId: string) => {
    setTurns((prev) => {
      if (!(sessionId in prev)) {
        return prev;
      }
      const { [sessionId]: _removed, ...rest } = prev;
      return rest;
    });
  }, []);

  return useMemo(() => ({ getTurn, upsertTurn, clearTurn }), [clearTurn, getTurn, upsertTurn]);
}
