import { createContext, useContext, type ReactNode } from "react";
import type { ApiError } from "../api/client";
import type { Readiness } from "../api/types";
import { useReadiness } from "./hooks";

const ReadinessContext = createContext<{ readiness: Readiness | null; error: ApiError | null }>({
  readiness: null,
  error: null,
});

export function ReadinessProvider({ children }: { children: ReactNode }) {
  const value = useReadiness();
  return <ReadinessContext.Provider value={value}>{children}</ReadinessContext.Provider>;
}

export const useReady = () => useContext(ReadinessContext);
