"use client";

import { useLayoutEffect, type RefObject } from "react";
import type { Model } from "@/lib/contracts";

type Props = {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
  pending: boolean;
  authenticated: boolean;
  models: Model[];
  model: string;
  onModelChange: (model: string) => void;
};

const MAX_LENGTH = 4000;

export function Composer({
  inputRef, value, onChange, onSubmit, busy, pending, authenticated, models, model, onModelChange,
}: Props) {
  const canSend = authenticated && !busy && Boolean(value.trim());

  useLayoutEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
  }, [inputRef, value]);

  return (
    <form className="composer" aria-label="Nueva pregunta" onSubmit={(event) => {
      event.preventDefault();
      if (canSend) onSubmit();
    }}>
      <div className="composer-box">
        <label htmlFor="question" className="sr-only">Pregunta</label>
        <textarea id="question" ref={inputRef} value={value} rows={1} maxLength={MAX_LENGTH}
                  placeholder="Pregunta sobre los informes…"
                  onChange={(event) => onChange(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing || event.keyCode === 229) return;
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }} />
        <div className="composer-toolbar">
          <label className="model-select">
            <span>Modelo</span>
            <select value={model} title={models.find((item) => item.slug === model)?.display_name}
                    onChange={(event) => onModelChange(event.target.value)} disabled={!models.length}>
              {models.length ? models.map((item) => <option key={item.slug} value={item.slug}>{item.display_name}</option>)
                : <option value="">{authenticated ? "Sin modelos disponibles" : "Al iniciar sesión"}</option>}
            </select>
          </label>
          {value.length > MAX_LENGTH - 500 ? <span className="composer-count" aria-live="polite">{value.length.toLocaleString("es")}/{MAX_LENGTH.toLocaleString("es")}</span> : null}
          <button type="submit" className="send-button" disabled={!canSend}
                  aria-label={pending ? "Consultando los datos" : "Enviar pregunta"} title="Enviar pregunta">
            <span aria-hidden="true">↑</span>
          </button>
        </div>
      </div>
    </form>
  );
}
