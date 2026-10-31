import type { Scenario } from '../types';

export function Controls({
  scenarios,
  selected,
  active,
  busy,
  onSelect,
  onAction,
}: {
  scenarios: Scenario[];
  selected: string;
  active: string;
  busy: boolean;
  onSelect: (id: string) => void;
  onAction: (kind: 'reset' | 'step' | 'run' | 'recover') => void;
}) {
  const scenario = scenarios.find((s) => s.id === selected);
  return (
    <section className="controls" aria-label="Scenario control">
      <div className="control-heading">
        <span className="eyebrow">SCENARIO CONTROL</span>
        <label htmlFor="scenario">Choose a failure boundary</label>
        <select
          id="scenario"
          value={selected}
          disabled={busy}
          onChange={(e) => onSelect(e.target.value)}
        >
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.title}
            </option>
          ))}
        </select>
        <p>{scenario?.description}</p>
      </div>
      <div className="control-actions">
        <button
          className="primary"
          disabled={busy || selected !== active}
          onClick={() => onAction('run')}
        >
          {busy ? 'Executing…' : 'Run'}
        </button>
        <button disabled={busy || selected !== active} onClick={() => onAction('step')}>
          Step
        </button>
        <button disabled={busy || selected !== active} onClick={() => onAction('recover')}>
          Recover
        </button>
        <button disabled={busy} onClick={() => onAction('reset')}>
          Reset / seed
        </button>
        <small>
          {selected !== active
            ? 'Reset / seed to load this scenario.'
            : `Expected terminal: ${scenario?.expected ?? '—'}`}
        </small>
      </div>
    </section>
  );
}
