"use client";

import { useState, type FormEvent } from "react";
import type { UserFinancialState } from "@/types/financial";

const fields = [
  { key: "monthly_income", label: "Monthly income", required: true },
  { key: "additional_income", label: "Additional monthly income" },
  { key: "current_savings", label: "Current savings", required: true },
  { key: "recurring_expenses", label: "Monthly fixed expenses", required: true },
  { key: "discretionary_expenses", label: "Monthly flexible expenses" },
] as const;

export function FinancialSetup({ onSave }: { onSave: (state: UserFinancialState) => void }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSave({
      monthly_income: Number(values.monthly_income),
      additional_income: Number(values.additional_income || 0),
      current_savings: Number(values.current_savings),
      recurring_expenses: Number(values.recurring_expenses),
      discretionary_expenses: Number(values.discretionary_expenses || 0),
      upcoming_obligations: [],
      goals: [],
    });
  };

  return <section className="glass-panel-elevated p-6 sm:p-8">
    <p className="text-xs font-mono tracking-widest text-cyan-600 dark:text-cyan-400">START WITH YOUR OWN NUMBERS</p>
    <h2 className="text-2xl font-semibold mt-3">Set up your financial picture</h2>
    <p className="text-sm text-slate-600 dark:text-slate-300 mt-2">Enter your figures to see a useful summary. Add a purchase afterward to generate a projection.</p>
    <form onSubmit={submit} className="mt-7 grid gap-4 sm:grid-cols-2">
      {fields.map(({ key, label, ...field }) => <label key={key} className="text-sm font-medium">
        <span className="block mb-1.5">{label}{"required" in field ? " *" : ""}</span>
        <input className="input-field" type="number" min="0" step="0.01" inputMode="decimal"
          required={"required" in field} value={values[key] ?? ""} placeholder="Enter amount"
          onChange={e => setValues(current => ({ ...current, [key]: e.target.value }))} />
      </label>)}
      <div className="sm:col-span-2 mt-2"><button className="btn-primary" type="submit">Save financial picture</button></div>
    </form>
  </section>;
}
