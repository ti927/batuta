// app-team-workspace.jsx — Container do workspace com cabeçalho persistente + barra de abas + roteamento.
const { useState: useStateW, useEffect: useEffectW } = React;

const TABS = [
  { key: 'inicio', label: 'Início', icon: 'home' },
  { key: 'agentes', label: 'Agentes', icon: 'bot', count: () => window.CT.agentes.length },
  { key: 'instrumentos', label: 'Instrumentos', icon: 'wand', count: () => window.CT.instrumentos.length },
  { key: 'automacoes', label: 'Automações', icon: 'zap' },
  { key: 'execucoes', label: 'Execuções', icon: 'activity', count: () => window.CT_RUNS.length },
  { key: 'conversas', label: 'Conversas', icon: 'message', count: () => window.CT_CONVERSAS.length, alerta: () => window.CT_CONVERSAS.some(c => c.estado === 'andamento') },
];

function Toast({ msg }) {
  if (!msg) return null;
  return (
    <div className="toast-in" style={{ position: 'absolute', bottom: 24, right: 24, zIndex: 70, background: '#fff', border: '1px solid #C9E9D2', borderLeft: '3px solid #3DAA5C', borderRadius: 10, padding: '13px 16px', display: 'flex', gap: 10, alignItems: 'center', boxShadow: '0 8px 30px rgba(26,23,48,.14)' }}>
      <Icon name="checkCircle" size={20} color="#3DAA5C" />
      <div style={{ fontSize: 14, fontWeight: 500, color: '#1A1730' }}>{msg}</div>
    </div>
  );
}

function TeamWorkspace() {
  const T = window.CT;
  // estado de navegação persistido (sobrevive a refresh — útil em iteração de design)
  const initial = (() => {
    try { return JSON.parse(localStorage.getItem('batuta_team_nav') || '{}'); } catch (e) { return {}; }
  })();
  const [tab, setTab] = useStateW(initial.tab || 'inicio');
  const [openRun, setOpenRun] = useStateW(initial.openRun || null);
  const [agent, setAgent] = useStateW(null);
  const [instr, setInstr] = useStateW(null);
  const [toast, setToastState] = useStateW(null);
  const toastTimer = React.useRef(null);

  const showToast = (m) => { setToastState(m); clearTimeout(toastTimer.current); toastTimer.current = setTimeout(() => setToastState(null), 3600); };

  useEffectW(() => {
    try { localStorage.setItem('batuta_team_nav', JSON.stringify({ tab, openRun })); } catch (e) {}
  }, [tab, openRun]);

  const go = (t, runId) => { setOpenRun(runId || null); setTab(t); };

  let content;
  if (tab === 'inicio') content = <TabInicio go={go} onAgent={setAgent} />;
  else if (tab === 'agentes') content = <TabAgentes onAgent={setAgent} />;
  else if (tab === 'instrumentos') content = <TabInstrumentos onInstr={setInstr} />;
  else if (tab === 'automacoes') content = <TabAutomacoes onToast={showToast} />;
  else if (tab === 'execucoes') content = <TabExecucoes openRunId={openRun} onToast={showToast} />;
  else if (tab === 'conversas') content = <TabConversas onToast={showToast} />;

  const wide = tab === 'conversas';
  const full = tab === 'automacoes';

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, position: 'relative' }}>
      {/* cabeçalho persistente do time */}
      <div style={{ background: '#fff', borderBottom: '1px solid #E8E6F0', padding: '18px 32px 0' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 280 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 11, flexWrap: 'wrap' }}>
              <h1 style={{ fontSize: 23, fontWeight: 500, lineHeight: 1.2, fontFamily: "'Bricolage Grotesque',sans-serif" }}>{T.nome}</h1>
              <StatusBadge status="ativo" />
            </div>
            <p style={{ fontSize: 13.5, color: '#6B6880', marginTop: 5, maxWidth: 680, lineHeight: 1.5 }}>{T.resumo}</p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button className="btn-ghost" style={{ height: 38 }}><Icon name="sparkles" size={15} color="#6D4AFF" /> Conversar sobre o projeto</button>
            <button className="btn-primary" style={{ height: 38 }} onClick={() => showToast('Disparando execução de teste…')}><Icon name="play" size={15} /> Rodar agora</button>
          </div>
        </div>
        {/* barra de abas */}
        <div style={{ display: 'flex', gap: 2, marginTop: 16, overflowX: 'auto' }}>
          {TABS.map(t => {
            const active = tab === t.key;
            const n = t.count ? t.count() : null;
            const alerta = t.alerta && t.alerta();
            return (
              <button key={t.key} onClick={() => go(t.key)} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '11px 15px', cursor: 'pointer', font: 'inherit', border: 'none', background: 'transparent', fontSize: 14, fontWeight: 500, color: active ? '#6D4AFF' : '#6B6880', boxShadow: active ? 'inset 0 -2px 0 #6D4AFF' : 'none', whiteSpace: 'nowrap', position: 'relative' }}>
                <Icon name={t.icon} size={16} /> {t.label}
                {n != null && <span style={{ fontSize: 11.5, color: active ? '#6D4AFF' : '#A09DB8', background: active ? '#EFEAFF' : '#F0EEF6', padding: '0 7px', borderRadius: 999, minWidth: 20, textAlign: 'center', fontWeight: 500 }}>{n}</span>}
                {alerta && <span style={{ width: 7, height: 7, borderRadius: 999, background: '#6D4AFF' }} />}
              </button>
            );
          })}
        </div>
      </div>

      {/* conteúdo da aba */}
      <div style={{ flex: 1, overflowY: full ? 'hidden' : 'auto', background: '#FAFAF7', display: full ? 'flex' : 'block', minHeight: 0 }}>
        {full ? content : (
          <div style={{ maxWidth: wide ? 1100 : 1000, margin: '0 auto', padding: '0 32px', height: wide ? '100%' : 'auto' }}>
            {content}
          </div>
        )}
      </div>

      {agent && <AgentEditor a={agent} onClose={() => setAgent(null)} onToast={showToast} />}
      {instr && <InstrumentEditor inst={instr} onClose={() => setInstr(null)} onToast={showToast} />}
      <Toast msg={toast} />
    </div>
  );
}

function TeamApp() {
  return (
    <div style={{ display: 'flex', height: '100%', background: '#FAFAF7' }}>
      <TeamSidebar teamActive />
      <TeamWorkspace />
    </div>
  );
}

window.TeamApp = TeamApp;
