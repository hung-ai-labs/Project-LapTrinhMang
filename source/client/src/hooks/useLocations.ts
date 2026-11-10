import { useEffect, useRef, useState } from "react";
import { catalog, isConnectionError, type Province, type Ward } from "../lib/api";
import {
  PROVINCE_CACHE_KEY, ResourceLoader, readSelection, wardCacheKey, writeSelection,
} from "../lib/catalog";
import { useConnection } from "./useConnection";

const DEFAULT_PROVINCE_ID = "01";
const DEFAULT_WARD_ID = "00004";

const provincesCache = {
  key: PROVINCE_CACHE_KEY,
  parse: (raw: string): Province[] | null => {
    const value: unknown = JSON.parse(raw);
    return Array.isArray(value) ? (value as Province[]) : null;
  },
  serialize: (value: Province[]) => JSON.stringify(value),
};

const wardsCache = {
  key: "",
  parse: (raw: string): Ward[] | null => {
    const value: unknown = JSON.parse(raw);
    return Array.isArray(value) ? (value as Ward[]) : null;
  },
  serialize: (value: Ward[]) => JSON.stringify(value),
};

export function useLocations() {
  const { online, restored } = useConnection();
  const [provinces, setProvinces] = useState<Province[]>([]);
  const [provinceLoading, setProvinceLoading] = useState(true);
  const [provinceError, setProvinceError] = useState("");
  const [selection, setSelection] = useState(() => readSelection());
  const [wardCatalog, setWardCatalog] = useState<{
    provinceId: string | null; options: Ward[]; loading: boolean; error: string;
  }>({ provinceId: null, options: [], loading: false, error: "" });
  const [cachedProvinces, setCachedProvinces] = useState(false);
  const [cachedWards, setCachedWards] = useState(false);
  const [offlineSources, setOfflineSources] = useState({ provinces: false, wards: false });
  const markOffline = (source: "provinces" | "wards", offline: boolean) => {
    setOfflineSources((previous) => (
      previous[source] === offline ? previous : { ...previous, [source]: offline }
    ));
  };
  const provinceLoader = useRef<ResourceLoader<Province[]> | null>(null);
  const wardLoader = useRef<ResourceLoader<Ward[]> | null>(null);
  const { provinceId, wardId, wardName } = selection;

  useEffect(() => { writeSelection(selection); }, [selection]);

  useEffect(() => {
    const loader = new ResourceLoader<Province[]>({
      cache: provincesCache,
      load: (signal) => catalog<Province>("/provinces", signal),
      onValue: (records, fromCache) => {
        setProvinces(records);
        setCachedProvinces(fromCache);
        setSelection((current) => {
          if (records.some((row) => row.id === current.provinceId)) return current;
          const fallback = records.find((row) => row.id === DEFAULT_PROVINCE_ID);
          return { ...current, provinceId: fallback?.id ?? current.provinceId };
        });
      },
      onError: (message, error) => {
        if (isConnectionError(error)) {
          markOffline("provinces", true);
          return;
        }
        markOffline("provinces", false);
        setProvinceError(message);
      },
      onLoading: setProvinceLoading,
    });
    provinceLoader.current = loader;
    loader.start();
    return () => {
      loader.stop();
      provinceLoader.current = null;
    };
  }, []);

  useEffect(() => {
    if (!provinceId) {
      wardLoader.current = null;
      markOffline("wards", false);
      setWardCatalog({ provinceId: null, options: [], loading: false, error: "" });
      return;
    }
    const loader = new ResourceLoader<Ward[]>({
      cache: { ...wardsCache, key: wardCacheKey(provinceId) },
      load: (signal) => catalog<Ward>(
        `/wards?province_id=${encodeURIComponent(provinceId)}`, signal,
      ),
      onValue: (options, fromCache) => {
        setWardCatalog((current) => ({
          provinceId, options, loading: false, error: current.provinceId === provinceId ? current.error : "",
        }));
        setCachedWards(fromCache);
        setSelection((current) => {
          if (current.provinceId !== provinceId) return current;
          if (options.some((row) => row.id === current.wardId)) return current;
          const defaultWardId = provinceId === DEFAULT_PROVINCE_ID &&
            options.some((row) => row.id === DEFAULT_WARD_ID) ? DEFAULT_WARD_ID : null;
          const picked = options.find((row) => row.id === defaultWardId);
          return { provinceId, wardId: defaultWardId, wardName: picked?.name ?? current.wardName };
        });
      },
      onError: (message, error) => {
        if (isConnectionError(error)) {
          markOffline("wards", true);
          return;
        }
        markOffline("wards", false);
        setWardCatalog((current) => (
          current.provinceId === provinceId ? { ...current, loading: false, error: message } : current
        ));
      },
      onLoading: (loading) => setWardCatalog((current) => (
        current.provinceId === provinceId ? { ...current, loading } : current
      )),
    });
    wardLoader.current = loader;
    loader.start();
    return () => {
      loader.stop();
      wardLoader.current = null;
    };
  }, [provinceId]);

  useEffect(() => {
    if (restored === 0) return;
    provinceLoader.current?.refresh();
    wardLoader.current?.refresh();
  }, [restored]);

  const wards = provinceId && wardCatalog.provinceId === provinceId ? wardCatalog.options : [];
  const wardLoading = Boolean(provinceId) &&
    (wardCatalog.provinceId !== provinceId || wardCatalog.loading);
  const selectedWard = wards.find((row) => row.id === wardId) ?? null;
  const rememberedWard: Ward | null = !selectedWard && wardId ? {
    id: wardId,
    name: wardName ?? wardId,
    province_id: provinceId ?? "",
    administrative_type: null,
    latitude: null,
    longitude: null,
  } : null;
  const effectiveWard = selectedWard ?? wards[0] ?? rememberedWard;
  return {
    provinces, wards, provinceId,
    selectedWardId: selectedWard?.id ?? null,
    effectiveWardId: effectiveWard?.id ?? null,
    effectiveWard,
    historyEnabled: selectedWard !== null,
    province: provinces.find((row) => row.id === provinceId) ?? null,
    provinceLoading, wardLoading, online,
    offline: offlineSources.provinces || offlineSources.wards,
    catalogFromCache: cachedProvinces || cachedWards,
    error: provinceError || (wardCatalog.provinceId === provinceId ? wardCatalog.error : ""),
    selectProvince: (id: string) => setSelection({
      provinceId: id || null, wardId: null, wardName: null,
    }),
    selectWard: (id: string) => setSelection((current) => {
      const picked = wards.find((row) => row.id === id);
      return { ...current, wardId: picked ? id : null, wardName: picked?.name ?? null };
    }),
    reload: () => {
      provinceLoader.current?.refresh();
      wardLoader.current?.refresh();
    },
  };
}
