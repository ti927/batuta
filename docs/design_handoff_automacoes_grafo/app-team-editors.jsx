// app-team-editors.jsx — Editores em drawer: Agente (4 markdowns), Instrumento, e a aba Automações.
const { useState: useStateE } = React;

// ---------- Drawer genérico ----------
function Drawer({ children, onClose, width = 520 }) {
  React.useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);
  return (
    <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(26,23,48,.28)', zIndex: 40, display: 'flex', justifyContent: 'flex-end' }}>
      <div onClick={(e) => e.stopPropagation()} className="drawer-in" style={{ width, maxWidth: '94%', height: '100%', background: '#fff', borderLeft: '1px solid #E8E6F0', display: 'flex', flexDirection: 'column', boxShadow: '-12px 0 40px rgba(26,23,48,.12)' }}>
        {children}
      </div>
    </div>
  );
}

// ---------- Editor de Agente ----------
const DOC_FIELDS = [
  { key: 'agent', file: 'agent.md', label: 'Quem é', icon: 'bot', hint: 'A identidade e a função do agente.' },
  { key: 'skill', file: 'skill.md', label: 'Habilidades', icon: 'sparkles', hint: 'O que ele sabe fazer.' },
  { key: 'tools', file: 'tools.md', label: 'Cinto de instrumentos', icon: 'wand', hint: 'As ferramentas que ele pode usar.' },
  { key: 'soul', file: 'soul.md', label: 'Personalidade', icon: 'message', hint: 'O tom e o jeito de se comunicar.' },
];
function AgentEditor({ a, onClose, onToast }) {
  const [docs, setDocs] = useStateE({ ...a.docs });
  const [modelo, setModelo] = useStateE(a.modelo);
  const [tab, setTab] = useStateE('agent');
  const dirty = JSON.stringify(docs) !== JSON.stringify(a.docs) || modelo !== a.modelo;
  return (
    <Drawer onClose={onClose} width={560}>
      <div style={{ padding: '18px 22px', borderBottom: '1px solid #E8E6F0', display: 'flex', alignItems: 'flex-start', gap: 13 }}>
        <RobotFace color={a.cor} size={44} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 18, fontWeight: 500 }}>{a.nome}</span>
            {a.papel === 'inicial' && <span style={{ fontSize: 11, color: '#3D2A99', background: '#EFEAFF', padding: '1px 7px', borderRadius: 999, fontWeight: 500 }}>inicial</span>}
          </div>
          <div style={{ fontSize: 13, color: '#6B6880', marginTop: 3 }}>{a.resumo}</div>
        </div>
        <button onClick={onClose} aria-label="Fechar" style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: 4, color: '#6B6880' }}><Icon name="x" size={20} /></button>
      </div>

      {/* modelo + cinto */}
      <div style={{ padding: '14px 22px', borderBottom: '1px solid #E8E6F0', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <label style={{ fontSize: 12, fontWeight: 500, color: '#6B6880', display: 'block', marginBottom: 6 }}>Modelo de IA</label>
          <div style={{ display: 'flex', gap: 6 }}>
            {window.MODELOS.map(m => (
              <button key={m} onClick={() => setModelo(m)} style={{ flex: 1, cursor: 'pointer', font: 'inherit', fontSize: 12, padding: '7px 8px', borderRadius: 8, border: '1px solid ' + (modelo === m ? '#6D4AFF' : '#E8E6F0'), background: modelo === m ? '#F4F1FE' : '#fff', color: modelo === m ? '#3D2A99' : '#6B6880', fontWeight: modelo === m ? 500 : 400 }}>
                {m.replace('claude-', '')}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label style={{ fontSize: 12, fontWeight: 500, color: '#6B6880', display: 'block', marginBottom: 6 }}>Cinto de instrumentos</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {a.instrumentos.length ? a.instrumentos.map((i, k) => <span key={k} style={{ fontSize: 12.5, color: '#3D2A99', background: '#EFEAFF', padding: '5px 11px', borderRadius: 999, display: 'inline-flex', gap: 5, alignItems: 'center', fontWeight: 500 }}><Icon name={i.icon} size={13} /> {i.nome}</span>) : <span style={{ fontSize: 12.5, color: '#A09DB8' }}>Sem instrumentos</span>}
            <button style={{ fontSize: 12.5, color: '#6D4AFF', background: '#fff', border: '1px dashed #C9B8FF', padding: '5px 11px', borderRadius: 999, cursor: 'pointer', font: 'inherit', display: 'inline-flex', gap: 5, alignItems: 'center' }}><Icon name="plus" size={13} /> Adicionar</button>
          </div>
        </div>
      </div>

      {/* abas dos 4 markdowns */}
      <div style={{ padding: '0 22px', borderBottom: '1px solid #E8E6F0', display: 'flex', gap: 2 }}>
        {DOC_FIELDS.map(d => (
          <button key={d.key} onClick={() => setTab(d.key)} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '11px 10px', cursor: 'pointer', font: 'inherit', border: 'none', background: 'transparent', fontSize: 12.5, fontWeight: 500, color: tab === d.key ? '#6D4AFF' : '#6B6880', boxShadow: tab === d.key ? 'inset 0 -2px 0 #6D4AFF' : 'none' }}>
            <Icon name={d.icon} size={14} /> {d.label}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '18px 22px 28px' }}>
        {DOC_FIELDS.filter(d => d.key === tab).map(d => (
          <div key={d.key}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontFamily: 'ui-monospace,monospace', fontSize: 11.5, color: '#A09DB8', background: '#FAFAF7', border: '1px solid #E8E6F0', padding: '2px 8px', borderRadius: 5 }}>{d.file}</span>
              <span style={{ fontSize: 12.5, color: '#6B6880' }}>{d.hint}</span>
            </div>
            <textarea value={docs[d.key]} onChange={(e) => setDocs(s => ({ ...s, [d.key]: e.target.value }))}
              style={{ width: '100%', minHeight: 220, resize: 'vertical', border: '1px solid #E8E6F0', borderRadius: 10, padding: '14px 16px', fontSize: 13.5, lineHeight: 1.6, fontFamily: 'inherit', color: '#3a3850', outline: 'none', background: '#FAFAF7' }} />
            <button className="link-roxo" style={{ marginTop: 10, display: 'inline-flex', alignItems: 'center', gap: 6, background: '#F4F1FE', border: '1px solid #E6DEFB', borderRadius: 8, padding: '7px 12px', cursor: 'pointer', font: 'inherit', fontSize: 12.5, color: '#6D4AFF', fontWeight: 500 }}>
              <Icon name="sparkles" size={14} /> Melhorar este texto com a IA
            </button>
          </div>
        ))}
      </div>

      <div style={{ padding: '14px 22px', borderTop: '1px solid #E8E6F0', display: 'flex', gap: 10, alignItems: 'center' }}>
        <button className="btn-primary" style={{ height: 40, opacity: dirty ? 1 : .55, pointerEvents: dirty ? 'auto' : 'none' }} onClick={() => { onToast('Agente salvo'); onClose(); }}><Icon name="check" size={16} /> Salvar alterações</button>
        <button className="btn-ghost" style={{ height: 40 }} onClick={onClose}>Cancelar</button>
        <div style={{ flex: 1 }} />
        <button aria-label="Remover" style={{ border: 'none', background: 'transparent', color: '#E5484D', cursor: 'pointer', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 5 }}><Icon name="x" size={15} /> Remover</button>
      </div>
    </Drawer>
  );
}

// ---------- Editor de Instrumento ----------
function InstrumentEditor({ inst, onClose, onToast }) {
  const [aprov, setAprov] = useStateE(inst.exigeAprovacao);
  return (
    <Drawer onClose={onClose} width={480}>
      <div style={{ padding: '18px 22px', borderBottom: '1px solid #E8E6F0', display: 'flex', alignItems: 'flex-start', gap: 13 }}>
        <span style={{ width: 44, height: 44, borderRadius: 11, background: '#EFEAFF', display: 'grid', placeItems: 'center', flex: 'none' }}><Icon name={inst.icon} size={22} color="#6D4AFF" /></span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <span style={{ fontSize: 18, fontWeight: 500 }}>{inst.nome}</span>
          <div style={{ fontSize: 12.5, color: '#A09DB8', fontFamily: 'ui-monospace,monospace', marginTop: 3 }}>{inst.slug}</div>
        </div>
        <button onClick={onClose} aria-label="Fechar" style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: 4, color: '#6B6880' }}><Icon name="x" size={20} /></button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 18 }}>
        <div>
          <label style={{ fontSize: 12.5, fontWeight: 500, color: '#6B6880', display: 'block', marginBottom: 6 }}>Tipo</label>
          <div style={{ fontSize: 13.5, background: '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 8, padding: '10px 12px', display: 'inline-flex', alignItems: 'center', gap: 8 }}><Icon name={inst.icon} size={15} color="#6D4AFF" /> {inst.tipo}</div>
        </div>
        <div>
          <label style={{ fontSize: 12.5, fontWeight: 500, color: '#6B6880', display: 'block', marginBottom: 6 }}>O que faz</label>
          <p style={{ fontSize: 13.5, color: '#3a3850', lineHeight: 1.6 }}>{inst.descricao}</p>
        </div>
        <div style={{ background: '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 10, padding: '14px 16px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          <Icon name="shield" size={18} color={aprov ? '#E89638' : '#A09DB8'} style={{ marginTop: 1 }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 500 }}>Exigir aprovação humana</div>
            <div style={{ fontSize: 12.5, color: '#6B6880', marginTop: 2, lineHeight: 1.5 }}>Antes de usar este instrumento, o agente pausa e espera seu ok. Recomendado para ações que não dão pra desfazer.</div>
          </div>
          <button onClick={() => setAprov(v => !v)} role="switch" aria-checked={aprov} style={{ width: 42, height: 24, borderRadius: 999, border: 'none', cursor: 'pointer', background: aprov ? '#6D4AFF' : '#D6D3E8', position: 'relative', flex: 'none', transition: 'background .15s' }}>
            <span style={{ position: 'absolute', top: 3, left: aprov ? 21 : 3, width: 18, height: 18, borderRadius: 999, background: '#fff', transition: 'left .15s' }} />
          </button>
        </div>
        <div>
          <label style={{ fontSize: 12.5, fontWeight: 500, color: '#6B6880', display: 'block', marginBottom: 6 }}>Usado por</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {inst.usadoPor.map((n, k) => <span key={k} style={{ fontSize: 12.5, color: '#6B6880', background: '#FAFAF7', border: '1px solid #E8E6F0', padding: '4px 10px', borderRadius: 999 }}>{n}</span>)}
          </div>
        </div>
      </div>
      <div style={{ padding: '14px 22px', borderTop: '1px solid #E8E6F0', display: 'flex', gap: 10 }}>
        <button className="btn-primary" style={{ height: 40 }} onClick={() => { onToast('Instrumento salvo'); onClose(); }}><Icon name="check" size={16} /> Salvar</button>
        <button className="btn-ghost" style={{ height: 40 }} onClick={onClose}>Cancelar</button>
      </div>
    </Drawer>
  );
}

window.AgentEditor = AgentEditor;
window.InstrumentEditor = InstrumentEditor;
// TabAutomacoes agora vive em app-team-automacoes.jsx (construtor de grafo).
