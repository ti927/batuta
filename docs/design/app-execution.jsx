// app-execution.jsx — Inspeção de execução passo a passo + espera-por-humano
const { useState: useStateExec, useRef: useRefExec } = React;

function StepDot({ estado }) {
  const map = {
    ok: { bg: '#3DAA5C', icon: 'check', ring: '#E6F4EA' },
    aguardando: { bg: '#E89638', icon: 'clock', ring: '#FDF1E3' },
    rodando: { bg: '#6D4AFF', icon: 'loader', ring: '#EFEAFF' },
    pendente: { bg: '#D6D3E8', icon: null, ring: '#F0EEF6' },
    falhou: { bg: '#E5484D', icon: 'x', ring: '#FDECEC' },
  };
  const s = map[estado] || map.pendente;
  return (
    <span style={{ width: 30, height: 30, borderRadius: 999, background: s.ring, display: 'grid', placeItems: 'center', flex: 'none', zIndex: 1 }}>
      <span style={{ width: 20, height: 20, borderRadius: 999, background: s.bg, display: 'grid', placeItems: 'center' }}>
        {s.icon && <Icon name={s.icon} size={13} color="#fff" spin={estado === 'rodando'} />}
      </span>
    </span>
  );
}

function FieldBlock({ label, children, tone }) {
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 11.5, fontWeight: 500, color: '#A09DB8', textTransform: 'uppercase', letterSpacing: '.04em', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 13.5, color: '#3a3850', lineHeight: 1.55, background: tone || '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 8, padding: '9px 12px' }}>{children}</div>
    </div>
  );
}

function ExecStep({ step, agentes, expanded, onToggle, last }) {
  let title, sub, robot = null;
  if (step.tipo === 'gatilho') { title = step.titulo; }
  else if (step.tipo === 'portao') { title = step.titulo; }
  else if (step.tipo === 'fim') { title = step.titulo; }
  else { const a = agentes.find(x => x.id === step.ref); title = a.nome; robot = a; }
  const canExpand = step.entrada || step.saida || step.pergunta;
  return (
    <div style={{ display: 'flex', gap: 14, position: 'relative' }}>
      {/* trilha */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 'none' }}>
        <StepDot estado={step.estado} />
        {!last && <div style={{ width: 2, flex: 1, minHeight: 18, background: '#EDEBF4', margin: '2px 0' }} />}
      </div>
      {/* card */}
      <div style={{ flex: 1, paddingBottom: 16, minWidth: 0 }}>
        <div onClick={canExpand ? onToggle : undefined}
          style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, padding: '12px 14px', cursor: canExpand ? 'pointer' : 'default' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {robot ? <RobotFace color={robot.cor} size={28} lider={robot.papel === 'lider'} />
              : <span style={{ width: 28, height: 28, borderRadius: 8, background: step.tipo === 'portao' ? '#FDF1E3' : '#F0EEF6', display: 'grid', placeItems: 'center' }}><Icon name={step.tipo === 'gatilho' ? 'zap' : step.tipo === 'portao' ? 'message' : 'globe'} size={15} color={step.tipo === 'portao' ? '#E89638' : '#6B6880'} /></span>}
            <span style={{ fontSize: 14.5, fontWeight: 500, flex: 1 }}>{title}</span>
            {step.tokens && <span style={{ fontSize: 12, color: '#A09DB8' }}>{step.tokens} tokens</span>}
            {step.dur && step.dur !== '—' && <span style={{ fontSize: 12, color: '#A09DB8' }}>{step.dur}</span>}
            {canExpand && <Icon name="chevronDown" size={16} color="#C9C3E0" style={{ transform: expanded ? 'none' : 'rotate(-90deg)', transition: 'transform .15s' }} />}
          </div>
          {step.detalhe && <div style={{ fontSize: 13, color: '#6B6880', marginTop: 7, lineHeight: 1.5 }}>{step.detalhe}</div>}
          {!expanded && step.saida && step.saida !== '—' && (
            <div style={{ fontSize: 13, color: '#6B6880', marginTop: 7, lineHeight: 1.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{step.saida}</div>
          )}
          {expanded && (
            <div style={{ marginTop: 4 }}>
              {step.entrada && step.entrada !== '—' && <FieldBlock label="Recebeu">{step.entrada}</FieldBlock>}
              {step.pergunta && (
                <FieldBlock label="Perguntou a um humano (pergunta pontual)" tone="#FBF7E9">
                  <div style={{ color: '#1A1730' }}>{step.pergunta.q}</div>
                  <div style={{ marginTop: 6, color: '#3DAA5C', display: 'flex', gap: 6, alignItems: 'flex-start' }}><Icon name="check" size={15} style={{ marginTop: 2 }} /> <span>{step.pergunta.a}</span></div>
                </FieldBlock>
              )}
              {step.saida && step.saida !== '—' && <FieldBlock label="Produziu">{step.saida}</FieldBlock>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// As três formas de espera-por-humano (legenda)
function FormasLegenda() {
  const itens = [
    { icon: 'circleHelp', t: 'Pergunta pontual', d: 'O agente precisa de um dado pra seguir.' },
    { icon: 'shield', t: 'Portão de aprovação', d: 'Um humano autoriza antes de um passo importante.' },
    { icon: 'alert', t: 'Confirmação de baixa confiança', d: 'Na dúvida, o agente confirma em vez de errar.' },
  ];
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 14 }}>
      {itens.map((i, k) => (
        <div key={k} style={{ flex: 1, minWidth: 180, display: 'flex', gap: 9, alignItems: 'flex-start', background: '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 9, padding: '10px 12px' }}>
          <Icon name={i.icon} size={16} color="#6D4AFF" style={{ marginTop: 1 }} />
          <div><div style={{ fontSize: 12.5, fontWeight: 500 }}>{i.t}</div><div style={{ fontSize: 11.5, color: '#6B6880', marginTop: 2, lineHeight: 1.4 }}>{i.d}</div></div>
        </div>
      ))}
    </div>
  );
}

function ApprovalGate({ artigo, onApprove, onAdjust, working }) {
  const [mode, setMode] = useStateExec(null); // null | 'adjust'
  const [nota, setNota] = useStateExec('');
  return (
    <div style={{ background: 'linear-gradient(135deg,#FFFDF8,#FBF7E9)', border: '1px solid #F0E2C0', borderRadius: 12, padding: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 4 }}>
        <Icon name="message" size={18} color="#E89638" />
        <span style={{ fontSize: 15, fontWeight: 500, color: '#1A1730' }}>O fluxo está esperando você</span>
        <ExecBadge estado="aguardando_humano" />
      </div>
      <p style={{ fontSize: 13.5, color: '#6B6880', lineHeight: 1.55 }}>O líder mandou o rascunho no WhatsApp. Publicar é uma ação que não dá pra desfazer — nada vai pro ar sem o seu ok.</p>

      <div style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, padding: 14, marginTop: 14 }}>
        <div style={{ fontSize: 11.5, fontWeight: 500, color: '#A09DB8', textTransform: 'uppercase', letterSpacing: '.04em' }}>Rascunho pronto</div>
        <div style={{ fontSize: 16, fontWeight: 500, color: '#1A1730', marginTop: 5 }}>{artigo.titulo}</div>
        <div style={{ fontSize: 13, color: '#6B6880', marginTop: 4, lineHeight: 1.5 }}>{artigo.meta}</div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
          <span className="meta-chip">{artigo.palavras} palavras</span>
          <span className="meta-chip"><Icon name="archive" size={12} /> {artigo.categoria}</span>
          <span className="meta-chip"><Icon name="search" size={12} /> SEO ok</span>
        </div>
      </div>

      {mode !== 'adjust' ? (
        <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
          <button className="btn-primary" disabled={working} onClick={onApprove} style={{ height: 42, opacity: working ? .7 : 1 }}>
            {working ? <><Icon name="loader" size={16} spin /> Publicando…</> : <><Icon name="check" size={17} /> Aprovar e publicar</>}
          </button>
          <button className="btn-ghost" disabled={working} onClick={() => setMode('adjust')} style={{ height: 42 }}><Icon name="pencil" size={15} /> Pedir um ajuste</button>
        </div>
      ) : (
        <div style={{ marginTop: 14 }}>
          <textarea value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Diz o que mudar — o lure-writer recebe isso e reescreve antes de publicar."
            style={{ width: '100%', minHeight: 70, resize: 'vertical', border: '1px solid #E8E6F0', borderRadius: 8, padding: '10px 12px', fontSize: 13.5, fontFamily: 'inherit', color: '#1A1730', outline: 'none' }} />
          <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
            <button className="btn-primary" onClick={() => onAdjust(nota)} style={{ height: 40 }}><Icon name="send" size={15} /> Enviar ajuste</button>
            <button className="btn-ghost" onClick={() => setMode(null)} style={{ height: 40 }}>Voltar</button>
          </div>
        </div>
      )}
      <FormasLegenda />
    </div>
  );
}

function ExecutionInspection({ exec, onBack }) {
  const E = window.EXEC;
  const startEstado = (exec && exec.estado) || 'aguardando_humano';
  const [status, setStatus] = useStateExec(startEstado);
  const [expanded, setExpanded] = useStateExec({ 3: true }); // curator (pergunta pontual) aberto
  const [working, setWorking] = useStateExec(false);
  const [toast, setToast] = useStateExec(null);
  const timers = useRefExec([]);

  // Deriva o estado de cada passo a partir do status geral
  const passos = E.passos.map((p) => {
    const np = { ...p };
    if (p.tipo === 'portao') {
      np.estado = status === 'aguardando_humano' ? 'aguardando' : (status === 'falhou' ? 'ok' : 'ok');
    } else if (p.ref === 'publisher') {
      np.estado = status === 'concluida' ? 'ok' : status === 'publicando' ? 'rodando' : status === 'falhou' ? 'falhou' : 'pendente';
      if (status === 'concluida') { np.saida = 'Publicado no WordPress com categoria, tags e resumo. Link gravado.'; np.dur = '4s'; np.tokens = '0,9k'; }
      if (status === 'falhou') { np.detalhe = 'WordPress não respondeu. Tentou 2 vezes, esperou e avisou o líder — nada publicado pela metade.'; }
    } else if (p.tipo === 'fim') {
      np.estado = status === 'concluida' ? 'ok' : 'pendente';
    }
    return np;
  });

  const onApprove = () => {
    setWorking(true);
    setStatus('publicando');
    const t = setTimeout(() => {
      setStatus('concluida'); setWorking(false); setExpanded((e) => ({ ...e, 6: true }));
      setToast('Artigo publicado ✨');
      setTimeout(() => setToast(null), 4000);
    }, 1900);
    timers.current.push(t);
  };
  const onAdjust = () => {
    setToast('Ajuste enviado ao lure-writer');
    setTimeout(() => setToast(null), 3500);
  };

  const portaoIdx = E.passos.findIndex((p) => p.tipo === 'portao');
  const curStatus = status === 'publicando' ? 'em_andamento' : status;

  return (
    <div style={{ flex: 1, overflowY: 'auto', background: '#FAFAF7', position: 'relative' }}>
      <div style={{ maxWidth: 820, margin: '0 auto', padding: '26px 32px 64px' }}>
        <button onClick={onBack} className="link-back" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'transparent', border: 'none', cursor: 'pointer', font: 'inherit', fontSize: 13.5, color: '#6B6880', padding: 0, marginBottom: 16 }}>
          <Icon name="chevronRight" size={15} style={{ transform: 'rotate(180deg)' }} /> Voltar ao time
        </button>

        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
              <h1 style={{ fontSize: 24, fontWeight: 500, lineHeight: 1.2, fontFamily: "'Bricolage Grotesque',sans-serif" }}>Execução <span style={{ fontFamily: 'ui-monospace,monospace', fontSize: 19, color: '#6B6880' }}>{E.id}</span></h1>
              <ExecBadge estado={curStatus} size={13} />
            </div>
            <div style={{ fontSize: 13.5, color: '#6B6880', marginTop: 6, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name="zap" size={14} /> {E.gatilho}</span>
              <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name="clock" size={14} /> {E.quando}</span>
              <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name="gauge" size={14} /> {status === 'concluida' ? 'R$ 0,38' : E.custoAteAgora} até agora</span>
            </div>
          </div>
        </div>

        {/* Painel de aprovação quando pausado */}
        {status === 'aguardando_humano' && (
          <div style={{ marginTop: 22 }}>
            <ApprovalGate artigo={E.artigo} onApprove={onApprove} onAdjust={onAdjust} working={working} />
          </div>
        )}

        <SectionLabel icon="layers">Passo a passo</SectionLabel>
        <div>
          {passos.map((p, i) => (
            <ExecStep key={i} step={p} agentes={window.TEAM.agentes}
              expanded={!!expanded[i]} onToggle={() => setExpanded((e) => ({ ...e, [i]: !e[i] }))}
              last={i === passos.length - 1} />
          ))}
        </div>
      </div>

      {toast && (
        <div className="toast-in" style={{ position: 'absolute', bottom: 24, right: 24, zIndex: 60, background: '#fff', border: '1px solid #C9E9D2', borderLeft: '3px solid #3DAA5C', borderRadius: 10, padding: '13px 16px', display: 'flex', gap: 10, alignItems: 'center', boxShadow: '0 8px 30px rgba(26,23,48,.14)' }}>
          <Icon name="checkCircle" size={20} color="#3DAA5C" />
          <div style={{ fontSize: 14, fontWeight: 500, color: '#1A1730' }}>{toast}</div>
        </div>
      )}
    </div>
  );
}

window.ExecutionInspection = ExecutionInspection;
