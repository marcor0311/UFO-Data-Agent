"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from "react";
import { flushSync } from "react-dom";
import type { Catalog, CertifiedSummary, ConversationSummary, GoldResult, Model, Session, Turn } from "@/lib/contracts";
import { ApiError, api } from "@/lib/api";
import { AmbientParticles } from "./ambient-particles";
import { CatalogViews } from "./catalog-views";
import { Composer } from "./composer";
import { groupResults, ResultPanel, resultTitle } from "./result-panel";
import { TurnView } from "./turn";
import { ModelViewer } from "@/components/views/model-viewer";
import { modelCatalogIntent, type ModelKind } from "@/lib/map-models";
import { MapAreaContext, type MapArea } from "@/lib/map-area";

const STORAGE = "ufo-agent-conversation";
const PANES = {
  chat: { title: "Conversación", hash: "", id: "chat-panel" },
  explore: { title: "Explorar datos", hash: "#explorar-datos", id: "explorar-datos" },
  certified: { title: "Consultas de ejemplo", hash: "#consultas-de-ejemplo", id: "consultas-de-ejemplo" },
};
const STARTER_QUERIES = [
  "CQ01_REPORTS_BY_SOURCE", "CQ02_REPORTS_BY_YEAR", "CQ08_COUNTRY_MAP",
  "CQ04_SEASONALITY_BY_MONTH", "CQ07_TOP_COUNTRIES", "CQ09_TOP_SHAPES",
];

type WorkspaceView = keyof typeof PANES;
type Failure = { message: string; status: number; retry?: boolean };

const savedConversation = {
  get() {
    try { return window.localStorage.getItem(STORAGE); } catch { return null; }
  },
  set(id: string) {
    try { window.localStorage.setItem(STORAGE, id); } catch { /* The active conversation still works. */ }
  },
  clear() {
    try { window.localStorage.removeItem(STORAGE); } catch { /* Storage can be disabled. */ }
  },
};

function viewFromHash(hash: string): WorkspaceView {
  if (hash === PANES.certified.hash || hash === "#consultas-certificadas") return "certified";
  if (hash === PANES.explore.hash) return "explore";
  return "chat";
}

function exampleTurn(item: CertifiedSummary, result: GoldResult): Turn {
  return {
    question: item.examples[0] ?? item.title,
    answer: `${item.description} ${item.limitation}`,
    visualizations: [result], trace: [{ tool: "run_certified", ok: true }], model: "", load_id: result.provenance.gold_load_id,
    created_at: new Date().toISOString(),
  };
}

function failureFrom(error: unknown, fallback: string): Failure {
  return error instanceof ApiError
    ? { message: error.code?.startsWith("certified_") ? fallback : error.message, status: error.status }
    : { message: fallback, status: 0 };
}

export default function AgentWorkspace() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [model, setModel] = useState<string>("");
  const [mapArea, setMapArea] = useState<MapArea | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [selectedTurn, setSelectedTurn] = useState<number | null>(null);
  const [view, setView] = useState<WorkspaceView>("chat");
  const [modelsOpen, setModelsOpen] = useState(false);
  const [modelsInitial, setModelsInitial] = useState<ModelKind | "all">("all");
  const [moreIdeas, setMoreIdeas] = useState(false);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [startupError, setStartupError] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const log = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  const history = useRef<HTMLDetailsElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const chatHeading = useRef<HTMLHeadingElement>(null);
  const resultsBody = useRef<HTMLDivElement>(null);
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const authenticated = Boolean(session?.authenticated);
  const busy = pending !== null || restoring;
  const activeIndex = selectedTurn ?? turns.length - 1;
  const activeTurn = turns[activeIndex];
  const groups = activeTurn ? groupResults(activeTurn.visualizations) : [];
  const pane = PANES[view];
  const starters = STARTER_QUERIES
    .map((id) => catalog?.certified_queries.find((item) => item.id === id && item.valid))
    .filter((item) => item !== undefined);

  const loadConversations = useCallback(() => {
    api<ConversationSummary[]>("agent/conversations").then(setConversations).catch(() => setConversations([]));
  }, []);

  const displayView = useCallback((next: WorkspaceView, animate: boolean, focusHeading = false) => {
    const update = () => {
      setView(next);
      if (focusHeading) requestAnimationFrame(() => chatHeading.current?.focus({ preventScroll: true }));
    };
    if (animate && document.startViewTransition && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      document.startViewTransition(() => flushSync(update));
    } else {
      update();
    }
  }, []);

  useEffect(() => {
    api<Catalog>("agent/catalog").then(setCatalog).catch((e: ApiError) => setStartupError(e.message));
    api<Session>("auth/status").then((s) => {
      setSession(s);
      if (!s.authenticated) return;
      api<{ models: Model[]; selected: string }>("agent/models")
        .then((m) => { setModels(m.models); setModel(m.selected); })
        .catch((error) => setFailure(failureFrom(error, "No se pudieron cargar los modelos.")));
      loadConversations();
      const saved = savedConversation.get();
      if (saved) {
        setRestoring(true);
        api<{ turns: Turn[] }>(`agent/conversations/${saved}`)
          .then((c) => { setConversationId(saved); setTurns(c.turns); })
          .catch(savedConversation.clear)
          .finally(() => setRestoring(false));
      }
    }).catch((error) => setAuthError(failureFrom(error, "No se pudo verificar la sesión.").message));
  }, [loadConversations]);

  useEffect(() => {
    setView(viewFromHash(window.location.hash));
    const syncView = () => {
      const hash = window.location.hash;
      const next = viewFromHash(hash);
      if (!hash || next !== "chat") displayView(next, true);
    };
    window.addEventListener("hashchange", syncView);
    return () => window.removeEventListener("hashchange", syncView);
  }, [displayView]);

  useLayoutEffect(() => {
    if (view === "chat" && followLatest.current && log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [turns, pending, view, failure, restoring]);

  useLayoutEffect(() => {
    if (resultsBody.current && selectedTurn === null) resultsBody.current.scrollTop = 0;
  }, [activeTurn, selectedTurn]);

  function appendTurn(turn: Turn) {
    setModelsOpen(false);
    setTurns((current) => [...current, turn]);
    const count = turn.visualizations.length;
    setAnnouncement(`Respuesta recibida con ${count} ${count === 1 ? "resultado" : "resultados"}.`);
  }

  async function ask() {
    const question = draft.trim();
    if (!question || busy) return;
    // "ver modelos 3d": show the 3D model catalog inline in Resultados; no model call needed.
    const catalogKind = modelCatalogIntent(question);
    if (catalogKind) {
      setDraft("");
      setModelsInitial(catalogKind);
      setModelsOpen(true);
      return;
    }
    if (!authenticated) return;
    followLatest.current = true;
    setPending(question);
    setDraft("");
    setFailure(null);
    try {
      const result = await api<{ conversation_id: string; turn: Turn }>("agent/chat", { question, conversation_id: conversationId, model: model || null, ...(mapArea ? { area: mapArea.polygon } : {}) });
      setConversationId(result.conversation_id);
      savedConversation.set(result.conversation_id);
      appendTurn(result.turn);
      loadConversations();
    } catch (e) {
      setFailure({ ...failureFrom(e, "No se pudo completar la consulta."), retry: true });
      setDraft((current) => current.trim() ? current : question);
    } finally {
      setPending(null);
    }
  }

  async function runCertified(item: CertifiedSummary) {
    if (busy || !item.valid) return;
    followLatest.current = true;
    if (view !== "chat") navigate("chat", undefined, true);
    setPending(item.examples[0] ?? item.title);
    setFailure(null);
    try {
      const result = await api<GoldResult>(`agent/certified/${item.id}`);
      appendTurn(exampleTurn(item, result));
    } catch (e) {
      setFailure(failureFrom(e, "No se pudo ejecutar la consulta de ejemplo."));
    } finally {
      setPending(null);
    }
  }

  async function open(id: string) {
    followLatest.current = true;
    setRestoring(true);
    setFailure(null);
    if (history.current) history.current.open = false;
    chatHeading.current?.focus();
    try {
      const c = await api<{ turns: Turn[] }>(`agent/conversations/${id}`);
      setConversationId(id);
      setTurns(c.turns);
      setSelectedTurn(null);
      savedConversation.set(id);
    } catch (e) {
      setFailure(failureFrom(e, "No se pudo abrir la conversación."));
    } finally {
      setRestoring(false);
    }
  }

  function navigate(next: WorkspaceView, event?: MouseEvent<HTMLAnchorElement>, focusHeading = false) {
    if (event) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
    }
    const { hash, pathname, search } = window.location;
    const nextHash = PANES[next].hash;
    if (hash !== nextHash && (viewFromHash(hash) !== "chat" || nextHash)) {
      window.history.pushState(null, "", pathname + search + nextHash);
    }
    if (view !== next) displayView(next, view === "explore" || next === "explore", focusHeading);
  }

  function prepare(question: string) {
    setDraft(question);
    navigate("chat");
    requestAnimationFrame(() => input.current?.focus());
  }

  function showResults(index: number) {
    followLatest.current = false;
    setSelectedTurn(index);
    setModelsOpen(false);
    const results = turns[index].visualizations;
    const primary = results.find((result) => result.view !== "table") ?? results[0];
    if (primary) setAnnouncement(`Mostrando ${resultTitle(primary, catalog)}, de la respuesta ${index + 1}.`);
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth";
    requestAnimationFrame(() => {
      const body = resultsBody.current;
      if (!body) return;
      resultsHeading.current?.focus({ preventScroll: true });
      resultsHeading.current?.scrollIntoView({ block: "nearest", behavior });
      body.scrollTo({ top: 0, behavior });
    });
  }

  function showLatestResults() {
    setSelectedTurn(null);
    setModelsOpen(false);
    setAnnouncement("Mostrando la respuesta más reciente.");
    requestAnimationFrame(() => {
      resultsHeading.current?.focus({ preventScroll: true });
      resultsHeading.current?.scrollIntoView({ block: "nearest" });
    });
  }

  function focusQuestion() {
    navigate("chat");
    requestAnimationFrame(() => input.current?.focus());
  }

  function reset() {
    followLatest.current = true;
    setConversationId(null);
    setTurns([]);
    setSelectedTurn(null);
    setMoreIdeas(false);
    setFailure(null);
    setAnnouncement("");
    if (history.current) history.current.open = false;
    savedConversation.clear();
    input.current?.focus();
  }

  const logout = async () => {
    await api("auth/logout", {}).catch(() => null);
    savedConversation.clear();
    window.location.reload();
  };

  return (
    <MapAreaContext.Provider value={{ area: mapArea, setArea: setMapArea }}>
    <div className="workspace">
      <a className="skip-link" href={authenticated && view === "chat" ? "#question" : `#${pane.id}`}>Ir al panel principal</a>
      <header className="top">
        <span className="chat-brand">UFO <span>/ Data Agent</span></span>
        <nav className="chat-nav" aria-label="Secciones del agente">
          <a href="/agent" aria-current={view === "chat" ? "page" : undefined} onClick={(event) => navigate("chat", event)}>Conversación</a>
          <a href={PANES.explore.hash} aria-current={view !== "chat" ? "page" : undefined} onClick={(event) => navigate("explore", event)}>Explorar datos</a>
        </nav>
        <div className="session">
          {session === null ? null : authenticated ? (
            <>
              <span className="email" title={session.email}>{session.email}</span>
              <button type="button" className="ghost" onClick={logout} disabled={busy}>Cerrar sesión</button>
            </>
          ) : (
            <a className="button" href="/api/auth/start">Continuar con ChatGPT</a>
          )}
        </div>
      </header>
      <main className="layout">
        <section className="chat-panel" id={pane.id} tabIndex={-1} aria-labelledby="chat-title">
          <header className="chat-head">
            <h1 id="chat-title" ref={chatHeading} tabIndex={-1}>{pane.title}</h1>
            <div className="chat-actions">
              {view !== "chat" ? (
                <button type="button" className="chat-action" onClick={() => navigate(view === "explore" ? "chat" : "explore", undefined, true)}>
                  {view === "explore" ? "Volver a conversación" : "Volver a explorar"}
                </button>
              ) : null}
              {view === "chat" && authenticated ? (
                <details className="history" ref={history}>
                  <summary>Historial</summary>
                  <div className="history-content">
                    {conversations.length ? (
                      <ul className="conversation-list">
                        {conversations.map((c) => (
                          <li key={c.conversation_id}>
                            <button type="button" onClick={() => open(c.conversation_id)} disabled={busy}
                                    aria-current={c.conversation_id === conversationId ? "true" : undefined}>
                              {c.title || "Sin título"} <span>({c.turns})</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : <p>Aún no hay conversaciones guardadas.</p>}
                  </div>
                </details>
              ) : null}
              {view === "chat" && turns.length > 0 ? (
                <button type="button" className="chat-action" onClick={reset} disabled={busy}><span aria-hidden="true">+</span> Nueva conversación</button>
              ) : null}
            </div>
          </header>
          {(authError || startupError) && view !== "explore" ? <p className="banner" role="alert">{authError || startupError}</p> : null}
          <div className="chat-log" ref={log} role="log" aria-label="Mensajes" tabIndex={0} hidden={view !== "chat"}
               onScroll={(event) => {
                 const { scrollHeight, scrollTop, clientHeight } = event.currentTarget;
                 followLatest.current = scrollHeight - scrollTop - clientHeight < 80;
               }}>
            {!turns.length && !busy ? (
              <div className="chat-welcome">
                <h2>{session && !authenticated ? "Conecta tu cuenta para conversar" : "¿Qué quieres saber sobre los informes UFO?"}</h2>
                <p>{session && !authenticated
                  ? "La conversación usa el modelo de tu cuenta. Puedes probar las consultas públicas en Explorar datos."
                  : "Gold reúne informes de fenómenos aéreos no identificados. Los recuentos se expresan como rangos: todos los informes y excluyendo los posibles duplicados pendientes de revisión."}</p>
                {starters.length ? (
                  <>
                    <h3 id="starter-title">Para empezar</h3>
                    <ul id="starter-list" className="query-list starter-list" aria-labelledby="starter-title">
                      {starters.slice(0, moreIdeas ? starters.length : 3).map((item) => (
                        <li key={item.id}>
                          <button type="button" onClick={() => prepare(item.examples[0] ?? item.title)}>
                            {item.examples[0] ?? item.title}
                          </button>
                        </li>
                      ))}
                    </ul>
                    {starters.length > 3 ? (
                      <button type="button" className="chat-action" aria-controls="starter-list" aria-expanded={moreIdeas}
                              onClick={() => setMoreIdeas((expanded) => !expanded)}>{moreIdeas ? "Menos ideas" : "Más ideas"}</button>
                    ) : null}
                  </>
                ) : null}
              </div>
            ) : null}
            {turns.map((turn, index) => (
              <TurnView key={index} turn={turn} index={index} active={index === activeIndex} onShowResults={() => showResults(index)} />
            ))}
            {modelsOpen && !pending ? (
              <ModelViewer initial={modelsInitial} onClose={() => setModelsOpen(false)} />
            ) : pending ? (
              <div className="turn">
                <p className="turn-question"><span className="sr-only">Pregunta: </span>{pending}</p>
                <p className="pending" role="status"><span aria-hidden="true" />Consultando los datos…</p>
              </div>
            ) : null}
            {restoring ? <p className="pending" role="status">Recuperando la conversación…</p> : null}
            {failure ? (
              <div className="chat-error" role="alert">
                <p>{failure.status === 401 ? "Tu sesión venció. Vuelve a conectar tu cuenta." : failure.message}</p>
                {failure.status === 401 ? <a className="explore-link" href="/api/auth/start">Conectar de nuevo</a>
                  : failure.retry ? <p>Tu pregunta sigue en el campo para reintentarla.</p> : null}
              </div>
            ) : null}
          </div>
          {view === "chat" ? (
            <>
            {mapArea ? (
              <div className="area-chip" role="status">
                <span><strong>Área seleccionada activa</strong> ({mapArea.label}). Las próximas preguntas se limitan a ella.</span>
                <button type="button" onClick={() => setMapArea(null)}>Quitar área</button>
              </div>
            ) : null}
            <Composer inputRef={input} value={draft} onChange={setDraft} onSubmit={ask} busy={busy}
                      pending={pending !== null} authenticated={authenticated} models={models} model={model} onModelChange={setModel} />
            </>
          ) : view === "explore" ? (
            <div className="explore-panel">
              <h2>Explora los informes UFO</h2>
              <p>Consulta los datos públicos de Gold y sus{" "}
                <a className="explore-link" href={PANES.certified.hash} onClick={(event) => navigate("certified", event, true)}>
                  consultas de ejemplo
                </a>.
              </p>
              <p>
                <button type="button" className="explore-link" onClick={() => { setModelsInitial("all"); setModelsOpen(true); }}>Ver los modelos 3D de las 28 formas</button>
              </p>
              {catalog ? <CatalogViews views={catalog.views} /> : startupError
                ? <p role="alert">{startupError}</p>
                : <p role="status">Cargando el catálogo de datos…</p>}
            </div>
          ) : (
            <div className="catalog-panel">
              <p>Prueba preguntas sobre los datos públicos de Gold.</p>
              {catalog ? (
                <ul className="query-list">
                  {catalog.certified_queries.map((item) => (
                    <li key={item.id}>
                      <button type="button" onClick={() => runCertified(item)} disabled={busy || !item.valid} title={item.description}>
                        <span>{item.title}{!item.valid ? <em> (no disponible)</em> : null}</span>
                        <span aria-hidden="true">↗</span>
                      </button>
                      {authenticated && item.examples[0] ? (
                        <button type="button" className="ask-example" onClick={() => prepare(item.examples[0])} disabled={busy}
                                aria-label={`Usar la pregunta: ${item.examples[0]}`}>Preparar</button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : !startupError ? <p role="status">Cargando el catálogo…</p> : null}
            </div>
          )}
        </section>

        <section className="results-panel" id="resultados" aria-label="Resultados">
          <p className="sr-only" role="status">{announcement}</p>
          {activeTurn && !modelsOpen ? (
            <header className="results-head">
              <h2 ref={resultsHeading} tabIndex={-1}>Respuesta {activeIndex + 1} de {turns.length}</h2>
              <div className="results-actions">
                {selectedTurn !== null ? (
                  <button type="button" className="chat-action" onClick={showLatestResults}>Volver al último resultado</button>
                ) : null}
                <button type="button" className="chat-action" onClick={focusQuestion}>Ir a la pregunta</button>
              </div>
            </header>
          ) : null}
          <div className="results-body" ref={resultsBody}>
            {modelsOpen && !pending ? (
              <ModelViewer initial={modelsInitial} onClose={() => setModelsOpen(false)} />
            ) : pending && selectedTurn === null ? (
              <div className="results-loading" role="status" aria-label="Consultando los datos">
                <div className="skeleton-line" aria-hidden="true" />
                <div className="skeleton-line skeleton-short" aria-hidden="true" />
                <div className="skeleton-chart" aria-hidden="true" />
              </div>
            ) : activeTurn && groups.length ? (
              <div className="results-stack" key={`${conversationId ?? "example"}-${activeIndex}-${activeTurn.created_at}`}>
                {groups.map((group) => (
                  <div className={group.length > 1 ? "result-group result-pair" : "result-group"} key={group[0].index}>
                    {group.map(({ result, index }) => <ResultPanel key={index} result={result} catalog={catalog} showTitle={activeTurn.visualizations.length > 1} />)}
                  </div>
                ))}
              </div>
            ) : activeTurn ? (
              <div className="results-empty">
                <h2>Esta respuesta no incluye visualizaciones</h2>
                <p>La explicación está en la conversación. Pide un gráfico o una cifra para ver aquí sus datos.</p>
              </div>
            ) : <AmbientParticles />}
          </div>
        </section>
      </main>
    </div>
    </MapAreaContext.Provider>
  );
}
