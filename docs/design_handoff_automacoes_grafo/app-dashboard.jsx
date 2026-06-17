// app-dashboard.jsx — Visão geral do time (Time de Blog SEO, ativo)
const { useState: useStateDash } = React;

const EXEC_STATE = {
  concluida: { bg: '#E6F4EA', fg: '#3DAA5C', label: 'concluída', icon: 'checkCircle' },
  aguardando_humano: { bg: '#FDF1E3', fg: '#E89638', label: 'aguardando você', icon: 'clock' },
  em_andamento: { bg: '#EFEAFF', fg: '#6D4AFF', label: 'em andamento', icon: 'loader' },
  falhou: { bg: '#FDECEC', fg: '#E5484D', label: 'falhou', icon: 'alert' },
};
function ExecBadge({ estado, size = 12 }) {
  const s = EXEC_STATE[estado] || EXEC_STATE.concluida;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: s.bg, color: s.fg, fontSize: size, fontWeight: 500, padding: '3px 9px 3px 7px', borderRadius: 999, whiteSpace: 'nowrap' }}>
      <Icon name={s.icon} size={size + 1} spin={estado === 'em_andamento'} /> {s.label}
    </span>
  );
}
window.ExecBadge = ExecBadge;
window.EXEC_STATE = EXEC_STATE;

// Cadeia horizontal (cabe na largura do dashboard)
function CadeiaFlowH() {
  const T = window.TEAM;
  const nodes = window.CADEIA;
  const chip = (children, tone) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#fff', border: '1px solid #E8E6F0', borderRadius: 9, padding: '8px 11px', whiteSpace: 'nowrap' }}>{children}</div>
  );
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      {nodes.map((n, i) => {
        let inner;
        if (n.tipo === 'gatilho') inner = chip(<><span style={{ width: 24, height: 24, borderRadius: 6, background: '#EFEAFF', display: 'grid', placeItems: 'center' }}><Icon name="clock" size={14} color="#6D4AFF" /></span><span style={{ fontSize: 13, fontWeight: 500 }}>8h, seg–sex</span></>);
        else if (n.tipo === 'agente') { const a = T.agentes.find(x => x.id === n.ref); inner = chip(<><RobotFace color={a.cor} size={24} lider={a.papel === 'lider'} /><span style={{ fontSize: 13, fontWeight: 500 }}>{a.nome}</span></>); }
        else if (n.tipo === 'portao') inner = chip(<><span style={{ width: 24, height: 24, borderRadius: 6, background: '#FDF1E3', display: 'grid', placeItems: 'center' }}><Icon name="message" size={14} color="#E89638" /></span><span style={{ fontSize: 13, fontWeight: 500, color: '#E89638' }}>Aprovação</span></>);
        else inner = chip(<><span style={{ width: 24, height: 24, borderRadius: 6, background: '#E6F4EA', display: 'grid', placeItems: 'center' }}><Icon name="checkCircle" size={14} color="#3DAA5C" /></span><span style={{ fontSize: 13, fontWeight: 500 }}>Publicado</span></>);
        return (
          <React.Fragment key={i}>
            {inner}
            {i < nodes.length - 1 && <Icon name="chevronRight" size={16} color="#C9C3E0" />}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function StatCard({ icon, tone, label, value, sub, onClick, accent }) {
  const [h, setH] = useStateDash(false);
  return (
    <div onClick={onClick} onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{ background: '#fff', border: '1px solid ' + (accent ? '#F0D9B8' : (h && onClick ? '#D6D3E8' : '#E8E6F0')), borderRadius: 12, padding: 18, cursor: onClick ? 'pointer' : 'default', transition: 'border-color .15s, transform .15s', transform: h && onClick ? 'translateY(-1px)' : 'none', flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 12 }}>
        <span style={{ width: 32, height: 32, borderRadius: 9, background: tone.bg, display: 'grid', placeItems: 'center' }}><Icon name={icon} size={17} color={tone.fg} /></span>
        <span style={{ fontSize: 13, color: '#6B6880' }}>{label}</span>
        {onClick && <Icon name="chevronRight" size={16} color="#C9C3E0" style={{ marginLeft: 'auto' }} />}
      </div>
      <div style={{ fontSize: 24, fontWeight: 500, color: '#1A1730', fontFamily: "'Bricolage Grotesque',sans-serif", lineHeight: 1.1 }}>{value}</div>
      <div style={{ fontSize: 12.5, color: accent ? '#E89638' : '#6B6880', marginTop: 4 }}>{sub}</div>
    </div>
  );
}

function Dashboard({ onOpenExecution, onOpenCompanion, onAgent }) {
  const T = window.TEAM;
  return (
    <div style={{ flex: 1, overflowY: 'auto', background: '#FAFAF7' }}>
      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 36px 64px' }}>
        {/* Cabeçalho */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <h1 style={{ fontSize: 26, fontWeight: 500, lineHeight: 1.2, color: '#1A1730', fontFamily: "'Bricolage Grotesque',sans-serif", whiteSpace: 'nowrap' }}>{T.nome}</h1>
              <StatusBadge status="ativo" />
            </div>
            <p style={{ fontSize: 14.5, color: '#6B6880', marginTop: 6 }}>{T.org} · publica um artigo otimizado por dia útil, com sua aprovação.</p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button className="btn-ghost" onClick={onOpenCompanion} style={{ height: 40 }}><Icon name="sparkles" size={16} color="#6D4AFF" /> Conversar sobre o projeto</button>
            <button className="btn-primary"><Icon name="play" size={16} /> Rodar agora</button>
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: 'flex', gap: 14, marginTop: 24, flexWrap: 'wrap' }}>
          <StatCard icon="clock" tone={{ bg: '#EFEAFF', fg: '#6D4AFF' }} label="Próxima execução" value="Amanhã, 8h" sub="pelo agendamento (seg–sex)" />
          <StatCard icon="message" tone={{ bg: '#FDF1E3', fg: '#E89638' }} label="Aguardando você" value="1 aprovação" sub="o artigo de hoje espera seu ok →" accent onClick={onOpenExecution} />
          <StatCard icon="gauge" tone={{ bg: '#E6F4EA', fg: '#3DAA5C' }} label="Custo no mês" value="R$ 6,84" sub="19 execuções · ~R$ 0,36 cada" />
        </div>

        {/* Cadeia */}
        <SectionLabel icon="layers">Cadeia · o caminho da tarefa</SectionLabel>
        <div style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 12, padding: 18 }}>
          <CadeiaFlowH />
        </div>

        {/* Execuções recentes */}
        <SectionLabel icon="activity">Execuções recentes</SectionLabel>
        <div style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 12, overflow: 'hidden' }}>
          {window.RECENTES.map((e, i) => (
            <button key={e.id} onClick={() => onOpenExecution(e)} className="row-btn"
              style={{ display: 'flex', alignItems: 'center', gap: 14, width: '100%', textAlign: 'left', font: 'inherit', cursor: 'pointer', background: 'transparent', border: 'none', borderTop: i ? '1px solid #F0EEF6' : 'none', padding: '13px 18px' }}>
              <span style={{ fontFamily: 'ui-monospace,monospace', fontSize: 13, color: '#6B6880', width: 52 }}>{e.id}</span>
              <span style={{ fontSize: 14, color: '#1A1730', width: 130 }}>{e.quando}</span>
              <ExecBadge estado={e.estado} />
              <span style={{ flex: 1 }} />
              {e.nota && <span style={{ fontSize: 12.5, color: '#A09DB8', maxWidth: 280, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.nota}</span>}
              <span style={{ fontSize: 13, color: '#6B6880', width: 78, textAlign: 'right' }}>{e.dur}</span>
              <span style={{ fontSize: 13, color: '#6B6880', width: 64, textAlign: 'right' }}>{e.custo}</span>
              <Icon name="chevronRight" size={16} color="#C9C3E0" />
            </button>
          ))}
        </div>

        {/* Agentes */}
        <SectionLabel icon="bot" count={T.agentes.length}>Agentes</SectionLabel>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {T.agentes.map((a) => <AgentCard key={a.id} a={a} onClick={() => onAgent(a)} />)}
        </div>
      </div>
    </div>
  );
}

window.Dashboard = Dashboard;
window.CadeiaFlowH = CadeiaFlowH;
