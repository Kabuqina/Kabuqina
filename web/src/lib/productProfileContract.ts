import { invoke } from "@tauri-apps/api/core";
import { useEffect, useState } from "react";

export type ProductProfileContract = {
  contractVersion: string;
  profile: string;
  visibleGateways: string[];
};

const CLOSED: ProductProfileContract = {
  contractVersion: "kabuqina.platform-surface/v1",
  profile: "invalid",
  visibleGateways: [],
};

export async function loadProductProfileContract(): Promise<ProductProfileContract> {
  try {
    return await invoke<ProductProfileContract>("cmd_product_profile_contract");
  } catch {
    return CLOSED;
  }
}

export function useProductProfileContract(): ProductProfileContract {
  const [contract, setContract] = useState<ProductProfileContract>(CLOSED);
  useEffect(() => {
    let active = true;
    void loadProductProfileContract().then((value) => {
      if (active) setContract(value);
    });
    return () => { active = false; };
  }, []);
  return contract;
}
