'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  createMetaConversionRule,
  fetchMetaConversionRules,
  patchMetaConversionRule,
} from '@/lib/meta/api';
import type { ConversionRuleRow, CreateConversionRuleBody } from '@/lib/meta/types';

export function useMetaConversionRules(token: string | null, clientId?: string) {
  const [rules, setRules] = useState<ConversionRuleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async () => {
    if (!token) {
      setRules([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const out = await fetchMetaConversionRules(token, clientId || undefined);
      setRules(out.rules ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Tải conversion rules thất bại');
      setRules([]);
    } finally {
      setLoading(false);
    }
  }, [token, clientId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const saveRule = useCallback(
    async (body: CreateConversionRuleBody) => {
      if (!token) return;
      setSaving(true);
      setError('');
      try {
        await createMetaConversionRule(token, body);
        await reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Lưu rule thất bại');
      } finally {
        setSaving(false);
      }
    },
    [token, reload],
  );

  const toggleRule = useCallback(
    async (ruleId: string, enabled: boolean) => {
      if (!token) return;
      setSaving(true);
      setError('');
      try {
        await patchMetaConversionRule(token, ruleId, { enabled });
        await reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Cập nhật rule thất bại');
      } finally {
        setSaving(false);
      }
    },
    [token, reload],
  );

  return { rules, loading, error, saving, reload, saveRule, toggleRule };
}
