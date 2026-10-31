import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, request } from './api';
import type { Order, Scenario, Snapshot } from './types';

export function useLab() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selected, setSelected] = useState('happy');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const running = useRef(false);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    const value = await request<Snapshot>('/system');
    if (mounted.current) setSnapshot(value);
    return value;
  }, []);

  const reconnect = useCallback(async () => {
    setError(null);
    try {
      const [value, catalog] = await Promise.all([refresh(), request<Scenario[]>('/scenarios')]);
      if (!mounted.current) return;
      setScenarios(catalog);
      setSelected(value.orders[0]?.scenario ?? 'happy');
    } catch (e) {
      if (mounted.current) setError(String(e));
    }
  }, [refresh]);

  useEffect(() => {
    mounted.current = true;
    void reconnect();
    return () => {
      mounted.current = false;
      running.current = false;
    };
  }, [reconnect]);

  const act = async (kind: 'reset' | 'step' | 'run' | 'recover') => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setError(null);
    try {
      const id = snapshot?.orders[0]?.id;
      if (kind === 'reset') {
        await request(`/scenarios/${encodeURIComponent(selected)}/reset`, 'POST');
        await refresh();
      } else if (kind === 'recover') {
        await request('/recovery/run', 'POST');
        await refresh();
      } else if (id) {
        // Run is real step playback: each frame follows a committed backend response.
        for (let i = 0; i < (kind === 'run' ? 32 : 1); i++) {
          const order = await request<Order>(`/orders/${id}/step`, 'POST');
          await refresh();
          if (['DONE', 'MANUAL_REVIEW'].includes(order.state) || !mounted.current) break;
        }
      }
    } catch (e) {
      setError(e instanceof ApiError ? `${e.code}: ${e.message}` : String(e));
      await refresh().catch(() => undefined);
    } finally {
      running.current = false;
      if (mounted.current) setBusy(false);
    }
  };

  return { snapshot, scenarios, selected, setSelected, busy, error, act, reconnect };
}
