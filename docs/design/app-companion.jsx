// app-companion.jsx — IA companheira: conversa viva sobre o projeto, com memória (Virada 3)
const { useState: useStateComp, useEffect: useEffectComp, useRef: useRefComp } = React;

function MemoriaPanel() {
  const M = window.MEMORIA;
  const blocos = [
    { icon: 'layers', titulo: 'Estado atual', itens: M.estado, note: 'consultado ao vivo no banco' },
    { icon: 'activity', titulo: 'Últimas execuções', itens: M.execucoes, note: 'histórico do projeto' },
    { icon: 'sparkles', titulo: 'Decisões lembradas', itens: M.decisoes, note: 'memória de longo prazo' },
  ];
  return (
    <div style={{ flex: 1, overflowY: 'auto', background: '#FAFAF7' }}>
      <div style={{ padding: '24px 28px 48px', maxWidth: 460, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="library" size={16} color="#6D4AFF" />
          <span style={{ fontSize: 14, fontWeight: 500 }}>O que eu sei deste projeto</span>
        </div>
        <p style={{ fontSize: 12.5, color: '#6B6880', marginTop: 6, lineHeight: 1.5 }}>Eu não fui criada agora — acompanho o time desde que ele nasceu. Puxo o estado atual quando preciso e guardo o que importa.</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 18 }}>
          {blocos.map((b, k) => (
            <div key={k} style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 12, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{ width: 28, height: 28, borderRadius: 8, background: '#EFEAFF', display: 'grid', placeItems: 'center' }}><Icon name={b.icon} size={15} color="#6D4AFF" /></span>
                <span style={{ fontSize: 14, fontWeight: 500 }}>{b.titulo}</span>
                <span style={{ fontSize: 10.5, color: '#A09DB8', marginLeft: 'auto' }}>{b.note}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {b.itens.map((it, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 13.5, color: '#3a3850' }}>
                    <span style={{ width: 5, height: 5, borderRadius: 999, background: '#B19CD9', marginTop: 7, flex: 'none' }} />
                    <span style={{ lineHeight: 1.45 }}>{it}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CompanionScreen() {
  const STEPS = window.COMPANION_STEPS;
  const [messages, setMessages] = useStateComp([]);
  const [typing, setTyping] = useStateComp(false);
  const [step, setStep] = useStateComp(-1);
  const [chips, setChips] = useStateComp(null);
  const [proposal, setProposal] = useStateComp(false);
  const [applied, setApplied] = useStateComp(false);
  const [toast, setToast] = useStateComp(false);
  const [draft, setDraft] = useStateComp('');
  const scrollRef = useRefComp(null);
  const timers = useRefComp([]);

  const advanceTo = (idx) => {
    const s = STEPS[idx]; if (!s) return;
    setChips(null); setTyping(true);
    const t = setTimeout(() => {
      setTyping(false);
      setMessages((m) => [...m, { role: 'ai', text: s.ai }]);
      if (s.effect === 'proposeChange') setProposal(true);
      if (!s.final) setChips(s.chips);
      setStep(idx);
    }, idx === 0 ? 450 : 900);
    timers.current.push(t);
  };
  useEffectComp(() => { advanceTo(0); return () => timers.current.forEach(clearTimeout); }, []);
  useEffectComp(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [messages, typing, chips, proposal]);

  const pick = (text) => { setMessages((m) => [...m, { role: 'user', text }]); setChips(null); advanceTo(step + 1); };
  const send = () => { const v = draft.trim(); if (!v) return; setDraft(''); pick(v); };
  const apply = () => {
    setApplied(true); setProposal(false);
    setMessages((m) => [...m, { role: 'user', text: 'Pode aplicar' }, { role: 'ai', text: 'Feito. O gatilho agora dispara às 7h em dias úteis. A próxima execução já sai no horário novo.' }]);
    setToast(true); setTimeout(() => setToast(false), 4000);
  };

  return (
    <div style={{ flex: 1, display: 'flex', position: 'relative', minHeight: 0 }}>
      {/* Chat */}
      <div style={{ width: 460, flex: 'none', borderRight: '1px solid #E8E6F0', display: 'flex', flexDirection: 'column', background: '#fff' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #E8E6F0', display: 'flex', alignItems: 'center', gap: 11 }}>
          <span style={{ width: 34, height: 34, borderRadius: 9, background: 'linear-gradient(135deg,#3DD8C3,#6D4AFF)', display: 'grid', placeItems: 'center' }}><Icon name="sparkles" size={18} color="#fff" /></span>
          <div>
            <div style={{ fontSize: 15, fontWeight: 500 }}>IA companheira</div>
            <div style={{ fontSize: 12, color: '#6B6880' }}>Conhece o Time de Blog SEO desde o início</div>
          </div>
        </div>
        <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {messages.map((m, i) => (
            <div key={i} className="rise" style={{ alignSelf: m.role === 'ai' ? 'flex-start' : 'flex-end', maxWidth: '88%' }}>
              <div style={m.role === 'ai'
                ? { background: '#F4F1FE', color: '#2A2150', borderRadius: '4px 14px 14px 14px', padding: '11px 14px', fontSize: 14, lineHeight: 1.55 }
                : { background: '#1A1730', color: '#fff', borderRadius: '14px 14px 4px 14px', padding: '11px 14px', fontSize: 14, lineHeight: 1.55 }}>{m.text}</div>
            </div>
          ))}
          {typing && <div className="rise" style={{ alignSelf: 'flex-start' }}><div style={{ background: '#F4F1FE', borderRadius: '4px 14px 14px 14px', padding: '13px 16px', display: 'flex', gap: 5 }}><span className="td" /><span className="td" style={{ animationDelay: '.15s' }} /><span className="td" style={{ animationDelay: '.3s' }} /></div></div>}
          {!typing && chips && chips.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-start' }}>
              {chips.map((c, i) => <button key={i} className="chip-btn" onClick={() => pick(c)}>{c}</button>)}
            </div>
          )}
          {!typing && proposal && !applied && (
            <div className="rise" style={{ background: 'linear-gradient(135deg,#F4F1FE,#FBF7E9)', border: '1px solid #E6DEFB', borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 11.5, fontWeight: 500, color: '#A09DB8', textTransform: 'uppercase', letterSpacing: '.04em' }}>Mudança proposta · rascunho</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '10px 0', fontSize: 14 }}>
                <span style={{ color: '#A09DB8', textDecoration: 'line-through' }}>8h</span>
                <Icon name="arrowRight" size={15} color="#6D4AFF" />
                <span style={{ fontWeight: 500, color: '#1A1730' }}>7h</span>
                <span style={{ fontSize: 12.5, color: '#6B6880' }}>· seg–sex</span>
              </div>
              <button className="btn-primary" onClick={apply} style={{ width: '100%', justifyContent: 'center', height: 40 }}><Icon name="check" size={16} /> Aplicar mudança</button>
            </div>
          )}
        </div>
        <div style={{ padding: '14px 18px', borderTop: '1px solid #E8E6F0' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', background: '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 10, padding: '8px 8px 8px 14px' }}>
            <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') send(); }} placeholder="Pergunta ou peça algo sobre o projeto…"
              style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontSize: 14, color: '#1A1730', fontFamily: 'inherit' }} />
            <button onClick={send} aria-label="Enviar" className="btn-primary" style={{ width: 36, height: 36, padding: 0, borderRadius: 8 }}><Icon name="send" size={16} /></button>
          </div>
        </div>
      </div>
      {/* Memória do projeto */}
      <MemoriaPanel />
      {toast && (
        <div className="toast-in" style={{ position: 'absolute', bottom: 24, right: 24, zIndex: 60, background: '#fff', border: '1px solid #C9E9D2', borderLeft: '3px solid #3DAA5C', borderRadius: 10, padding: '13px 16px', display: 'flex', gap: 10, alignItems: 'center', boxShadow: '0 8px 30px rgba(26,23,48,.14)' }}>
          <Icon name="checkCircle" size={20} color="#3DAA5C" />
          <div><div style={{ fontSize: 14, fontWeight: 500, color: '#1A1730' }}>Horário atualizado</div><div style={{ fontSize: 12.5, color: '#6B6880' }}>Agora dispara às 7h em dias úteis.</div></div>
        </div>
      )}
    </div>
  );
}

window.CompanionScreen = CompanionScreen;
