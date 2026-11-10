import { useEffect, useState } from "react";
import { catalog, type Province, type Ward } from "../lib/api";

const DEFAULT_PROVINCE_ID = "01";
const DEFAULT_WARD_ID = "00004";

export function useLocations() {
  const [provinces, setProvinces] = useState<Province[]>([]);
  const [provinceLoading, setProvinceLoading] = useState(true);
  const [provinceError, setProvinceError] = useState("");
  const [selection, setSelection] = useState<{
    provinceId: string | null; wardId: string | null;
  }>({ provinceId: null, wardId: null });
  const [wardCatalog, setWardCatalog] = useState<{
    provinceId: string | null; options: Ward[]; loading: boolean; error: string;
  }>({ provinceId: null, options: [], loading: false, error: "" });
  const [revision, setRevision] = useState(0);
  const { provinceId, wardId } = selection;

  useEffect(() => {
    const controller = new AbortController();
    setProvinceLoading(true);
    setProvinceError("");
    void catalog<Province>("/provinces", controller.signal).then((records) => {
      if (controller.signal.aborted) return;
      setProvinces(records);
      setSelection((current) => {
        if (records.some((row) => row.id === current.provinceId)) return current;
        const fallback = records.find((row) => row.id === DEFAULT_PROVINCE_ID);
        return { provinceId: fallback?.id ?? null, wardId: null };
      });
    }).catch((error) => {
      if (!controller.signal.aborted) {
        setProvinceError(error instanceof Error ? error.message : "Không tải được tỉnh/thành.");
      }
    }).finally(() => {
      if (!controller.signal.aborted) setProvinceLoading(false);
    });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    if (!provinceId) return;
    const controller = new AbortController();
    setWardCatalog({ provinceId, options: [], loading: true, error: "" });
    void catalog<Ward>(
      `/wards?province_id=${encodeURIComponent(provinceId)}`, controller.signal,
    ).then((options) => {
      if (controller.signal.aborted) return;
      setWardCatalog({ provinceId, options, loading: false, error: "" });
      setSelection((current) => {
        if (current.provinceId !== provinceId) return current;
        if (options.some((row) => row.id === current.wardId)) return current;
        const defaultWardId = provinceId === DEFAULT_PROVINCE_ID &&
          options.some((row) => row.id === DEFAULT_WARD_ID) ? DEFAULT_WARD_ID : null;
        return { provinceId, wardId: defaultWardId };
      });
    }).catch((error) => {
      if (!controller.signal.aborted) {
        setWardCatalog({
          provinceId, options: [], loading: false,
          error: error instanceof Error ? error.message : "Không tải được phường/xã.",
        });
      }
    });
    return () => controller.abort();
  }, [provinceId, revision]);

  const wards = provinceId && wardCatalog.provinceId === provinceId ? wardCatalog.options : [];
  const wardLoading = Boolean(provinceId) &&
    (wardCatalog.provinceId !== provinceId || wardCatalog.loading);
  const selectedWard = wards.find((row) => row.id === wardId) ?? null;
  const effectiveWard = selectedWard ?? wards[0] ?? null;
  return {
    provinces, wards, provinceId,
    selectedWardId: selectedWard?.id ?? null,
    effectiveWardId: effectiveWard?.id ?? null,
    effectiveWard,
    historyEnabled: selectedWard !== null,
    province: provinces.find((row) => row.id === provinceId) ?? null,
    provinceLoading, wardLoading,
    error: provinceError || (wardCatalog.provinceId === provinceId ? wardCatalog.error : ""),
    selectProvince: (id: string) => setSelection({ provinceId: id || null, wardId: null }),
    selectWard: (id: string) => setSelection((current) => ({
      ...current, wardId: wards.some((row) => row.id === id) ? id : null,
    })),
    reload: () => setRevision((current) => current + 1),
  };
}
