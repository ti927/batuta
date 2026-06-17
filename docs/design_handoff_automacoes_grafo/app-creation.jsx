// app-creation.jsx — O fluxo de criação AI-first: conversa + canvas do time em rascunho.
const { useState, useEffect, useRef, useCallback } = React;

// ---- Robozinho (no estilo dos robôs do mascote) ----
function RobotFace({ color, size = 40, lider }) {
  return (
    <div style={{ width: size, height: size, borderRadius: size * 0.32, background: color, display: 'grid', placeItems: 'center', position: 'relative', flex: 'none', boxShadow: 'inset 0 -' + (size * 0.06) + 'px 0 rgba(0,0,0,0.07)' }}>
      <div style={{ width: size * 0.6, height: size * 0.44, borderRadius: size * 0.16, background: 'rgba(20,16,40,0.85)', display: 'flex', gap: size * 0.12, alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ width: size * 0.12, height: size * 0.12, borderRadius: '50%', background: '#fff' }} />
        <span style={{ width: size * 0.12, height: size * 0.12, borderRadius: '50%', background: '#fff' }} />
      </div>
      {lider && (
        <svg width={size * 0.4} height={size * 0.4} viewBox="0 0 24 24" fill="#1A1730" style={{ position: 'absolute', top: -size * 0.16, right: -size * 0.14, filter: 'drop-shadow(0 1px 2px rgba(0,0,0,.15))' }}>
          <path d="m12 3-1.4 4.2a2 2 0 0 1-1.4 1.4L5 10l4.2 1.4a2 2 0 0 1 1.4 1.4L12 17l1.4-4.2a2 2 0 0 1 1.4-1.4L19 10l-4.2-1.4a2 2 0 0 1-1.4-1.4z" fill="#F5C44A" stroke="#1A1730" strokeWidth="1" />
        </svg>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  const draft = status !== 'ativo';
  const s = draft
    ? { bg: '#FDF1E3', fg: '#E89638', label: 'rascunho', icon: 'pencil' }
    : { bg: '#E6F4EA', fg: '#3DAA5C', label: 'ativo', icon: 'checkCircle' };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, background: s.bg, color: s.fg, fontSize: 12, fontWeight: 500, padding: '3px 9px 3px 7px', borderRadius: 999 }}>
      <Icon name={s.icon} size={13} /> {s.label}
    </span>
  );
}

// ---- Card de agente no canvas ----
function AgentCard({ a, onClick, delay = 0, active }) {
  const [hover, setHover] = useState(false);
  return (
    <button onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      className="rise"
      style={{
        textAlign: 'left', cursor: 'pointer', font: 'inherit', width: '100%',
        background: '#fff', border: '1px solid ' + (hover ? '#D6D3E8' : '#E8E6F0'), borderRadius: 10,
        padding: 14, display: 'flex', gap: 12, alignItems: 'flex-start',
        animationDelay: delay + 'ms', transition: 'border-color .15s, transform .15s, box-shadow .15s',
        transform: hover ? 'translateY(-1px)' : 'none', boxShadow: hover ? '0 4px 16px rgba(109,74,255,.08)' : 'none',
      }}>
      <RobotFace color={a.cor} size={40} lider={a.papel === 'lider'} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 500, fontSize: 15, color: '#1A1730' }}>{a.nome}</span>
          {a.papel === 'lider' && <span style={{ fontSize: 11, color: '#3D2A99', background: '#EFEAFF', padding: '1px 7px', borderRadius: 999, fontWeight: 500 }}>líder</span>}
        </div>
        <div style={{ fontSize: 13, color: '#6B6880', marginTop: 3, lineHeight: 1.45 }}>{a.resumo}</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 9, alignItems: 'center' }}>
          <span style={{ fontSize: 11.5, color: '#6B6880', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <Icon name="sparkles" size={12} color="#6D4AFF" /> {a.modelo}
          </span>
          {a.instrumentos.map((i, k) => (
            <span key={k} style={{ fontSize: 11.5, color: '#6B6880', display: 'inline-flex', alignItems: 'center', gap: 4, background: '#FAFAF7', border: '1px solid #E8E6F0', padding: '2px 8px', borderRadius: 999 }}>
              <Icon name={i.icon} size={12} /> {i.nome}
            </span>
          ))}
        </div>
      </div>
      <Icon name="chevronRight" size={16} color="#A09DB8" style={{ marginTop: 2 }} />
    </button>
  );
}

// ---- Nó da cadeia (pipeline vertical) ----
function CadeiaNode({ node, agentes, last }) {
  let body;
  if (node.tipo === 'gatilho') {
    body = (<><span style={{ width: 30, height: 30, borderRadius: 8, background: '#EFEAFF', display: 'grid', placeItems: 'center' }}><Icon name="zap" size={16} color="#6D4AFF" /></span><div><div style={{ fontSize: 14, fontWeight: 500 }}>Gatilho · agendamento</div><div style={{ fontSize: 12, color: '#6B6880' }}>Toda segunda a sexta, 8h</div></div></>);
  } else if (node.tipo === 'agente') {
    const a = agentes.find(x => x.id === node.ref);
    body = (<><RobotFace color={a.cor} size={30} lider={a.papel === 'lider'} /><div style={{ fontSize: 14, fontWeight: 500 }}>{a.nome}</div></>);
  } else if (node.tipo === 'portao') {
    body = (<><span style={{ width: 30, height: 30, borderRadius: 8, background: '#FDF1E3', display: 'grid', placeItems: 'center' }}><Icon name="message" size={16} color="#E89638" /></span><div><div style={{ fontSize: 14, fontWeight: 500 }}>Portão de aprovação</div><div style={{ fontSize: 12, color: '#E89638' }}>Espera você responder no WhatsApp</div></div></>);
  } else {
    body = (<><span style={{ width: 30, height: 30, borderRadius: 8, background: '#E6F4EA', display: 'grid', placeItems: 'center' }}><Icon name="checkCircle" size={16} color="#3DAA5C" /></span><div style={{ fontSize: 14, fontWeight: 500 }}>{node.label}</div></>);
  }
  return (
    <div style={{ position: 'relative', paddingLeft: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, padding: '10px 12px' }}>{body}</div>
      {!last && <div style={{ width: 2, height: 16, background: '#D6D3E8', margin: '2px 0 2px 21px' }} />}
    </div>
  );
}

// ---- Drawer de detalhe do agente (os 4 markdowns) ----
const DOCS = [
  { key: 'agent', file: 'agent.md', label: 'Quem é', icon: 'bot' },
  { key: 'skill', file: 'skill.md', label: 'Habilidades', icon: 'sparkles' },
  { key: 'tools', file: 'tools.md', label: 'Cinto de instrumentos', icon: 'wand' },
  { key: 'soul', file: 'soul.md', label: 'Personalidade', icon: 'message' },
];
function AgentDrawer({ a, onClose }) {
  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);
  if (!a) return null;
  return (
    <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(26,23,48,.28)', zIndex: 40, display: 'flex', justifyContent: 'flex-end' }}>
      <div onClick={(e) => e.stopPropagation()} className="drawer-in"
        style={{ width: 460, maxWidth: '92%', height: '100%', background: '#fff', borderLeft: '1px solid #E8E6F0', display: 'flex', flexDirection: 'column', boxShadow: '-12px 0 40px rgba(26,23,48,.12)' }}>
        <div style={{ padding: '18px 22px', borderBottom: '1px solid #E8E6F0', display: 'flex', alignItems: 'flex-start', gap: 13 }}>
          <RobotFace color={a.cor} size={44} lider={a.papel === 'lider'} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 18, fontWeight: 500 }}>{a.nome}</span>
              <StatusBadge status="rascunho" />
            </div>
            <div style={{ fontSize: 13, color: '#6B6880', marginTop: 3 }}>{a.resumo}</div>
          </div>
          <button onClick={onClose} aria-label="Fechar" style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: 4, color: '#6B6880', borderRadius: 6 }}><Icon name="x" size={20} /></button>
        </div>
        <div style={{ padding: '14px 22px', borderBottom: '1px solid #E8E6F0', display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <span style={{ fontSize: 12.5, color: '#3D2A99', background: '#EFEAFF', padding: '4px 10px', borderRadius: 999, display: 'inline-flex', gap: 5, alignItems: 'center', fontWeight: 500 }}><Icon name="sparkles" size={13} /> {a.modelo} · {a.tier}</span>
          {a.instrumentos.map((i, k) => <span key={k} style={{ fontSize: 12.5, color: '#6B6880', background: '#FAFAF7', border: '1px solid #E8E6F0', padding: '4px 10px', borderRadius: 999, display: 'inline-flex', gap: 5, alignItems: 'center' }}><Icon name={i.icon} size={13} /> {i.nome}</span>)}
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 22px 28px' }}>
          {DOCS.map((d) => (
            <div key={d.key} style={{ marginTop: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Icon name={d.icon} size={15} color="#6D4AFF" />
                <span style={{ fontSize: 14, fontWeight: 500 }}>{d.label}</span>
                <span style={{ fontFamily: 'ui-monospace,monospace', fontSize: 11.5, color: '#A09DB8', background: '#FAFAF7', border: '1px solid #E8E6F0', padding: '1px 7px', borderRadius: 5 }}>{d.file}</span>
              </div>
              <div style={{ fontSize: 13.5, color: '#3a3850', lineHeight: 1.6, whiteSpace: 'pre-wrap', background: '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 8, padding: '12px 14px' }}>{a.docs[d.key]}</div>
            </div>
          ))}
          <div style={{ marginTop: 22, display: 'flex', gap: 8 }}>
            <button className="btn-ghost"><Icon name="pencil" size={15} /> Ajustar com a IA</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---- Painel de chat (IA criadora) ----
function ChatPanel({ messages, typing, chips, onChip, onSend, finalAsk, onApprove, status }) {
  const [draft, setDraft] = useState('');
  const scrollRef = useRef(null);
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [messages, typing, chips, finalAsk]);
  const send = () => { const v = draft.trim(); if (!v) return; setDraft(''); onSend(v); };
  return (
    <div style={{ width: 440, flex: 'none', borderRight: '1px solid #E8E6F0', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #E8E6F0', display: 'flex', alignItems: 'center', gap: 11 }}>
        <span style={{ width: 34, height: 34, borderRadius: 9, background: 'linear-gradient(135deg,#6D4AFF,#8A6BFF)', display: 'grid', placeItems: 'center' }}><Icon name="sparkles" size={18} color="#fff" /></span>
        <div>
          <div style={{ fontSize: 15, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 7 }}>IA criadora</div>
          <div style={{ fontSize: 12, color: '#6B6880' }}>Monta o time com você, por conversa</div>
        </div>
      </div>

      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {messages.map((m, i) => (
          <div key={i} className="rise" style={{ alignSelf: m.role === 'ai' ? 'flex-start' : 'flex-end', maxWidth: '88%' }}>
            <div style={m.role === 'ai'
              ? { background: '#F4F1FE', color: '#2A2150', borderRadius: '4px 14px 14px 14px', padding: '11px 14px', fontSize: 14, lineHeight: 1.55 }
              : { background: '#1A1730', color: '#fff', borderRadius: '14px 14px 4px 14px', padding: '11px 14px', fontSize: 14, lineHeight: 1.55 }}>
              {m.text}
            </div>
          </div>
        ))}
        {typing && (
          <div className="rise" style={{ alignSelf: 'flex-start' }}>
            <div style={{ background: '#F4F1FE', borderRadius: '4px 14px 14px 14px', padding: '13px 16px', display: 'flex', gap: 5 }}>
              <span className="td" /><span className="td" style={{ animationDelay: '.15s' }} /><span className="td" style={{ animationDelay: '.3s' }} />
            </div>
          </div>
        )}
        {!typing && chips && chips.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-start', marginTop: 2 }}>
            {chips.map((c, i) => (
              <button key={i} onClick={() => onChip(c)} className="chip-btn">{c}</button>
            ))}
          </div>
        )}
        {!typing && finalAsk && status !== 'ativo' && (
          <div className="rise" style={{ marginTop: 4, background: 'linear-gradient(135deg,#F4F1FE,#FBF7E9)', border: '1px solid #E6DEFB', borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: 13.5, color: '#3D2A99', display: 'flex', gap: 8, marginBottom: 12 }}>
              <Icon name="shield" size={16} color="#6D4AFF" style={{ marginTop: 1 }} />
              <span>Tudo em rascunho. Ao aprovar, eu crio o time, os 5 agentes, o gatilho e a cadeia de uma vez.</span>
            </div>
            <button onClick={onApprove} className="btn-primary" style={{ width: '100%', justifyContent: 'center', height: 42 }}>
              <Icon name="check" size={17} /> Aprovar e criar time
            </button>
          </div>
        )}
        {!typing && status === 'ativo' && (
          <div className="rise" style={{ marginTop: 4, background: '#E6F4EA', border: '1px solid #C9E9D2', borderRadius: 12, padding: 16, display: 'flex', gap: 10 }}>
            <Icon name="checkCircle" size={18} color="#3DAA5C" style={{ marginTop: 1 }} />
            <div style={{ fontSize: 13.5, color: '#2C7A45' }}>Time criado ✨ Agora ele já existe de verdade — e eu continuo por aqui como IA companheira sempre que você quiser mexer nele.</div>
          </div>
        )}
      </div>

      <div style={{ padding: '14px 18px', borderTop: '1px solid #E8E6F0' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', background: '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 10, padding: '8px 8px 8px 14px' }}>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
            placeholder={status === 'ativo' ? 'Pedir um ajuste à IA companheira…' : 'Responder à IA criadora…'}
            style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontSize: 14, color: '#1A1730', fontFamily: 'inherit', padding: '4px 0' }} />
          <button onClick={send} aria-label="Enviar" className="btn-primary" style={{ width: 36, height: 36, padding: 0, borderRadius: 8 }}><Icon name="send" size={16} /></button>
        </div>
      </div>
    </div>
  );
}

// ---- Canvas do rascunho (direita) ----
function DraftCanvas({ canvas, onAgent, showMascot = true }) {
  const T = window.TEAM;
  return (
    <div style={{ flex: 1, overflowY: 'auto', background: '#FAFAF7' }}>
      <div style={{ maxWidth: 640, margin: '0 auto', padding: '28px 28px 60px' }}>
        {!canvas.teamVisible ? (
          <div style={{ marginTop: 90, textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            {showMascot
              ? <img src="assets/mascote.png" alt="Maestro da Batuta conduzindo os agentes" style={{ width: 280, maxWidth: '70%', opacity: .96 }} />
              : <span style={{ width: 84, height: 84, borderRadius: 22, background: '#EFEAFF', display: 'grid', placeItems: 'center', marginBottom: 6 }}><Icon name="layers" size={40} color="#6D4AFF" /></span>}
            <div style={{ fontSize: 18, fontWeight: 500, marginTop: 8, color: '#1A1730' }}>O time aparece aqui</div>
            <p style={{ fontSize: 14, color: '#6B6880', maxWidth: 340, marginTop: 6, lineHeight: 1.55 }}>Conforme você conversa com a IA, cada peça do time vai sendo montada deste lado — em rascunho, até você aprovar.</p>
          </div>
        ) : (
          <>
            <div className="rise" style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 4 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <h2 style={{ fontSize: 22, fontWeight: 500, color: '#1A1730' }}>{T.nome}</h2>
                  <StatusBadge status={canvas.status} />
                </div>
                <div style={{ fontSize: 13.5, color: '#6B6880', marginTop: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Icon name="users" size={14} /> {T.org} · cliente da consultoria
                </div>
              </div>
            </div>

            {/* Agentes */}
            <SectionLabel icon="bot" count={T.agentes.length}>Agentes</SectionLabel>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {T.agentes.map((a, i) => <AgentCard key={a.id} a={a} delay={i * 90} onClick={() => onAgent(a)} active={canvas.status === 'ativo'} />)}
            </div>

            {/* Gatilho */}
            {canvas.triggerVisible && (<>
              <SectionLabel icon="zap">Gatilho</SectionLabel>
              <div className="rise" style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, padding: 14, display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ width: 38, height: 38, borderRadius: 9, background: '#EFEAFF', display: 'grid', placeItems: 'center' }}><Icon name="clock" size={19} color="#6D4AFF" /></span>
                <div><div style={{ fontSize: 14.5, fontWeight: 500 }}>{T.gatilho.tipo}</div><div style={{ fontSize: 13, color: '#6B6880' }}>{T.gatilho.detalhe}</div></div>
              </div>
            </>)}

            {/* Cadeia */}
            {canvas.cadeiaVisible && (<>
              <SectionLabel icon="layers">Cadeia · o caminho da tarefa</SectionLabel>
              <div className="rise" style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 12, padding: 16 }}>
                {window.CADEIA.filter(n => n.tipo !== 'portao' || canvas.gateVisible).map((n, i, arr) => (
                  <CadeiaNode key={i} node={n} agentes={T.agentes} last={i === arr.length - 1} />
                ))}
              </div>
            </>)}

            {/* Custo */}
            {canvas.costVisible && (<>
              <SectionLabel icon="gauge">Custo estimado</SectionLabel>
              <div className="rise" style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 12, padding: 18, display: 'flex', gap: 20, alignItems: 'center' }}>
                <div><div style={{ fontSize: 26, fontWeight: 500, color: '#1A1730', fontFamily: "'Bricolage Grotesque',sans-serif" }}>{T.custo.porExec}</div><div style={{ fontSize: 12.5, color: '#6B6880' }}>por artigo</div></div>
                <div style={{ width: 1, alignSelf: 'stretch', background: '#E8E6F0' }} />
                <div><div style={{ fontSize: 26, fontWeight: 500, color: '#1A1730', fontFamily: "'Bricolage Grotesque',sans-serif" }}>{T.custo.porMes}</div><div style={{ fontSize: 12.5, color: '#6B6880' }}>{T.custo.chamadas} chamadas de IA por execução</div></div>
              </div>
            </>)}
          </>
        )}
      </div>
    </div>
  );
}
function SectionLabel({ icon, count, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '24px 0 12px' }}>
      <Icon name={icon} size={15} color="#6D4AFF" />
      <span style={{ fontSize: 13, fontWeight: 500, letterSpacing: '.02em', color: '#1A1730' }}>{children}</span>
      {count != null && <span style={{ fontSize: 12, color: '#A09DB8' }}>· {count}</span>}
      <span style={{ flex: 1, height: 1, background: '#E8E6F0', marginLeft: 4 }} />
    </div>
  );
}

// ---- Raiz do fluxo ----
function CreationFlow({ showMascot = true }) {
  const [messages, setMessages] = useState([]);
  const [typing, setTyping] = useState(false);
  const [step, setStep] = useState(-1);
  const [chips, setChips] = useState(null);
  const [finalAsk, setFinalAsk] = useState(false);
  const [selected, setSelected] = useState(null);
  const [toast, setToast] = useState(false);
  const [canvas, setCanvas] = useState({ teamVisible: false, status: 'rascunho', triggerVisible: false, cadeiaVisible: false, gateVisible: false, costVisible: false });
  const timers = useRef([]);

  const runEffects = useCallback((effects) => {
    if (!effects) return;
    setCanvas((c) => {
      const n = { ...c };
      effects.forEach((e) => {
        if (e === 'createTeam') n.teamVisible = true;
        if (e === 'setTrigger') n.triggerVisible = true;
        if (e === 'addGate') n.gateVisible = true;
        if (e === 'revealCadeia') n.cadeiaVisible = true;
        if (e === 'showCost') n.costVisible = true;
      });
      return n;
    });
  }, []);

  const advanceTo = useCallback((idx) => {
    const s = window.STEPS[idx];
    if (!s) return;
    setChips(null); setFinalAsk(false);
    setTyping(true);
    const t1 = setTimeout(() => {
      setTyping(false);
      runEffects(s.effects);
      setMessages((m) => [...m, { role: 'ai', text: s.ai }]);
      if (s.final) { setFinalAsk(true); }
      else { setChips(s.chips); }
      setStep(idx);
    }, idx === 0 ? 500 : 950);
    timers.current.push(t1);
  }, [runEffects]);

  useEffect(() => { advanceTo(0); return () => timers.current.forEach(clearTimeout); }, [advanceTo]);

  const pick = (text) => {
    setMessages((m) => [...m, { role: 'user', text }]);
    setChips(null);
    advanceTo(step + 1);
  };
  const onApprove = () => {
    setCanvas((c) => ({ ...c, status: 'ativo' }));
    setFinalAsk(false);
    setMessages((m) => [...m, { role: 'user', text: 'Aprovar e criar time' }]);
    setToast(true);
    setTyping(true);
    const t = setTimeout(() => {
      setTyping(false);
      setMessages((m) => [...m, { role: 'ai', text: 'Pronto! Criei o Time de Blog SEO com o líder, os 4 agentes, o gatilho e a cadeia. Ele já aparece na barra lateral.' }]);
    }, 1100);
    timers.current.push(t);
    setTimeout(() => setToast(false), 4200);
  };

  return (
    <div style={{ flex: 1, display: 'flex', position: 'relative', minHeight: 0 }}>
      <ChatPanel messages={messages} typing={typing} chips={chips} finalAsk={finalAsk} status={canvas.status}
        onChip={pick} onSend={pick} onApprove={onApprove} />
      <DraftCanvas canvas={canvas} onAgent={setSelected} showMascot={showMascot} />
      <AgentDrawer a={selected} onClose={() => setSelected(null)} />
      {toast && (
        <div className="toast-in" style={{ position: 'absolute', bottom: 24, right: 24, zIndex: 60, background: '#fff', border: '1px solid #C9E9D2', borderLeft: '3px solid #3DAA5C', borderRadius: 10, padding: '13px 16px', display: 'flex', gap: 10, alignItems: 'center', boxShadow: '0 8px 30px rgba(26,23,48,.14)' }}>
          <Icon name="checkCircle" size={20} color="#3DAA5C" />
          <div><div style={{ fontSize: 14, fontWeight: 500, color: '#1A1730' }}>Time criado ✨</div><div style={{ fontSize: 12.5, color: '#6B6880' }}>5 agentes, 1 gatilho e a cadeia, tudo de uma vez.</div></div>
        </div>
      )}
    </div>
  );
}

window.CreationFlow = CreationFlow;
window.RobotFace = RobotFace;
window.StatusBadge = StatusBadge;
window.AgentCard = AgentCard;
window.SectionLabel = SectionLabel;
window.AgentDrawer = AgentDrawer;
