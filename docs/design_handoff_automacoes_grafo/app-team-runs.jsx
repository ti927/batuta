// app-team-runs.jsx — Aba Execuções (lista + detalhe passo a passo, master-detail dentro da aba)
const { useState: useStateR } = React;

function RunStepDot({ estado }) {
  const map = {
    ok: { bg: '#3DAA5C', icon: 'check', ring: '#E6F4EA' },
    aguardando: { bg: '#E89638', icon: 'clock', ring: '#FDF1E3' },
    pendente: { bg: '#D6D3E8', icon: null, ring: '#F0EEF6' },
    falhou: { bg: '#E5484D', icon: 'x', ring: '#FDECEC' },
  };
  const s = map[estado] || map.pendente;
  return (
    <span style={{ width: 28, height: 28, borderRadius: 999, background: s.ring, display: 'grid', placeItems: 'center', flex: 'none', zIndex: 1 }}>
      <span style={{ width: 19, height: 19, borderRadius: 999, background: s.bg, display: 'grid', placeItems: 'center' }}>{s.icon && <Icon name={s.icon} size={12} color="#fff" />}</span>
    </span>
  );
}

function RunDetail({ run, onBack, onToast }) {
  const T = window.CT;
  const [expanded, setExpanded] = useStateR({});
  const [status, setStatus] = useStateR(run.estado);
  const [working, setWorking] = useStateR(false);
  const aguardando = status === 'aguardando_humano';

  const approve = () => {
    setWorking(true);
    setTimeout(() => { setWorking(false); setStatus('concluida'); onToast('Artigo publicado ✨'); }, 1700);
  };

  return (
    <div style={{ padding: '20px 0 60px' }}>
      <button onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'transparent', border: 'none', cursor: 'pointer', font: 'inherit', fontSize: 13.5, color: '#6B6880', padding: 0, marginBottom: 16 }}>
        <Icon name="chevronRight" size={15} style={{ transform: 'rotate(180deg)' }} /> Todas as execuções
      </button>

      <div style={{ display: 'flex', alignItems: 'center', gap: 11, flexWrap: 'wrap' }}>
        <h2 style={{ fontSize: 22, fontWeight: 500, fontFamily: "'Bricolage Grotesque',sans-serif", lineHeight: 1.2 }}>Execução <span style={{ fontFamily: 'ui-monospace,monospace', fontSize: 18, color: '#6B6880' }}>{run.id}</span></h2>
        <ExecBadge estado={status === 'concluida' ? 'concluida' : status} size={13} />
      </div>
      <div style={{ fontSize: 13.5, color: '#6B6880', marginTop: 6, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name="clock" size={14} /> {run.quando}</span>
        <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name="gauge" size={14} /> {run.custo}</span>
        <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name="message" size={14} /> {run.entrada}</span>
      </div>

      {/* portão de aprovação se pausado */}
      {aguardando && run.artigo && (
        <div style={{ marginTop: 20, background: 'linear-gradient(135deg,#FFFDF8,#FBF7E9)', border: '1px solid #F0E2C0', borderRadius: 12, padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 4 }}>
            <Icon name="message" size={18} color="#E89638" /><span style={{ fontSize: 15, fontWeight: 500 }}>O fluxo está esperando você</span>
          </div>
          <p style={{ fontSize: 13.5, color: '#6B6880', lineHeight: 1.55 }}>O Revisor de SEO terminou. Publicar não dá pra desfazer — nada vai pro ar sem o seu ok.</p>
          <div style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, padding: 14, marginTop: 12 }}>
            <div style={{ fontSize: 11.5, fontWeight: 500, color: '#A09DB8', textTransform: 'uppercase', letterSpacing: '.04em' }}>Rascunho pronto</div>
            <div style={{ fontSize: 16, fontWeight: 500, marginTop: 5 }}>{run.artigo.titulo}</div>
            <div style={{ fontSize: 13, color: '#6B6880', marginTop: 4, lineHeight: 1.5 }}>{run.artigo.meta}</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
              <span className="meta-chip">{run.artigo.palavras} palavras</span>
              <span className="meta-chip"><Icon name="archive" size={12} /> {run.artigo.categoria}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
            <button className="btn-primary" disabled={working} onClick={approve} style={{ height: 42, opacity: working ? .7 : 1 }}>{working ? <><Icon name="loader" size={16} spin /> Publicando…</> : <><Icon name="check" size={17} /> Aprovar e publicar</>}</button>
            <button className="btn-ghost" style={{ height: 42 }} disabled={working}><Icon name="pencil" size={15} /> Pedir ajuste</button>
          </div>
        </div>
      )}

      {/* timeline */}
      <SectionLabel icon="layers">Passo a passo</SectionLabel>
      <div>
        {run.passos.map((p, i) => {
          if (p.tipo === 'falha') {
            return (
              <div key={i} style={{ display: 'flex', gap: 14 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 'none' }}><RunStepDot estado="falhou" /></div>
                <div style={{ flex: 1, paddingBottom: 16 }}>
                  <div style={{ fontSize: 14.5, fontWeight: 500, color: '#E5484D', marginBottom: 6 }}>{p.titulo}</div>
                  <div style={{ background: '#FDECEC', border: '1px solid #F6CFD0', borderRadius: 10, padding: '11px 14px', fontSize: 13, color: '#B4282D', lineHeight: 1.5 }}>{p.erro}</div>
                </div>
              </div>
            );
          }
          const a = T.agentes.find(x => x.id === p.ref);
          const dotEstado = status === 'concluida' && p.estado === 'aguardando' ? 'ok' : p.estado;
          const canExp = p.saida || p.gate;
          const last = i === run.passos.length - 1;
          return (
            <div key={i} style={{ display: 'flex', gap: 14 }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 'none' }}>
                <RunStepDot estado={dotEstado} />
                {!last && <div style={{ width: 2, flex: 1, minHeight: 16, background: '#EDEBF4', margin: '2px 0' }} />}
              </div>
              <div style={{ flex: 1, paddingBottom: 16, minWidth: 0 }}>
                <div onClick={canExp ? () => setExpanded(e => ({ ...e, [i]: !e[i] })) : undefined} style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, padding: '12px 14px', cursor: canExp ? 'pointer' : 'default' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <RobotFace color={a.cor} size={26} />
                    <span style={{ fontSize: 14.5, fontWeight: 500, flex: 1 }}>{i + 1}. {a.nome}</span>
                    {p.gate && <span style={{ fontSize: 11, fontWeight: 500, color: p.gate.resolvido ? '#3DAA5C' : '#E89638', background: p.gate.resolvido ? '#E6F4EA' : '#FDF1E3', padding: '2px 8px', borderRadius: 999 }}>{p.gate.resolvido ? 'aprovado' : 'aguardando ok'}</span>}
                    {p.tokens && <span style={{ fontSize: 12, color: '#A09DB8' }}>{p.tokens} tok</span>}
                    {p.dur && <span style={{ fontSize: 12, color: '#A09DB8' }}>{p.dur}</span>}
                    {canExp && <Icon name="chevronDown" size={16} color="#C9C3E0" style={{ transform: expanded[i] ? 'none' : 'rotate(-90deg)', transition: 'transform .15s' }} />}
                  </div>
                  {!expanded[i] && p.saida && <div style={{ fontSize: 13, color: '#6B6880', marginTop: 7, lineHeight: 1.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.saida}</div>}
                  {expanded[i] && (
                    <div style={{ marginTop: 10 }}>
                      {p.gate && p.gate.resolvido && <div style={{ fontSize: 12.5, color: '#3DAA5C', marginBottom: 8, display: 'inline-flex', gap: 6, alignItems: 'center', background: '#E6F4EA', padding: '5px 10px', borderRadius: 8 }}><Icon name="check" size={14} /> {p.gate.decisao} por {p.gate.por}</div>}
                      <div style={{ fontSize: 11.5, fontWeight: 500, color: '#A09DB8', textTransform: 'uppercase', letterSpacing: '.04em', marginBottom: 4 }}>Produziu</div>
                      <div style={{ fontSize: 13.5, color: '#3a3850', lineHeight: 1.55, background: '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 8, padding: '9px 12px' }}>{p.saida}</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {run.uso && (
        <div style={{ marginTop: 8, background: '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 10, padding: '12px 16px' }}>
          <div style={{ fontSize: 12.5, color: '#6B6880' }}><b style={{ color: '#1A1730', fontWeight: 500 }}>Uso (estimado):</b> {run.uso}</div>
          <div style={{ fontSize: 11.5, color: '#A09DB8', marginTop: 2 }}>Custo aproximado, apenas informativo — não é cobrança.</div>
        </div>
      )}
    </div>
  );
}

function TabExecucoes({ openRunId, onToast }) {
  const [filtro, setFiltro] = useStateR('todas');
  const [sel, setSel] = useStateR(openRunId || null);
  React.useEffect(() => { if (openRunId) setSel(openRunId); }, [openRunId]);
  const runs = window.CT_RUNS;
  const selRun = runs.find(r => r.id === sel);
  if (selRun) return <RunDetail run={selRun} onBack={() => setSel(null)} onToast={onToast} />;

  const filtros = [
    { key: 'todas', label: 'Todas', n: runs.length },
    { key: 'concluida', label: 'Concluídas', n: runs.filter(r => r.estado === 'concluida').length },
    { key: 'aguardando_humano', label: 'Aguardando você', n: runs.filter(r => r.estado === 'aguardando_humano').length },
    { key: 'falhou', label: 'Falhou', n: runs.filter(r => r.estado === 'falhou').length },
  ];
  const lista = filtro === 'todas' ? runs : runs.filter(r => r.estado === filtro);

  return (
    <div style={{ padding: '24px 0 60px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
        <div><h2 style={{ fontSize: 17, fontWeight: 500 }}>Execuções</h2><p style={{ fontSize: 13.5, color: '#6B6880', marginTop: 3 }}>Todo disparo da automação. Abra uma para ver o passo a passo.</p></div>
        <div style={{ flex: 1 }} />
        <button className="btn-primary" style={{ height: 38 }} onClick={() => onToast('Disparando execução de teste…')}><Icon name="play" size={15} /> Rodar agora</button>
      </div>

      {/* stats */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        {[{ l: 'Total', v: runs.length, s: 'execuções' }, { l: 'Taxa de sucesso', v: '67%', s: '2 de 3' }, { l: 'Duração média', v: '1min 07s', s: 'por execução' }, { l: 'Custo total', v: '~US$ 0.74', s: 'estimado' }].map((c, i) => (
          <div key={i} style={{ flex: 1, minWidth: 140, background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, padding: 14 }}>
            <div style={{ fontSize: 12, color: '#6B6880' }}>{c.l}</div>
            <div style={{ fontSize: 20, fontWeight: 500, fontFamily: "'Bricolage Grotesque',sans-serif", marginTop: 4 }}>{c.v}</div>
            <div style={{ fontSize: 11.5, color: '#A09DB8', marginTop: 2 }}>{c.s}</div>
          </div>
        ))}
      </div>

      {/* filtros */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
        {filtros.map(f => (
          <button key={f.key} onClick={() => setFiltro(f.key)} style={{ cursor: 'pointer', font: 'inherit', fontSize: 13, padding: '7px 14px', borderRadius: 999, border: '1px solid ' + (filtro === f.key ? '#6D4AFF' : '#E8E6F0'), background: filtro === f.key ? '#6D4AFF' : '#fff', color: filtro === f.key ? '#fff' : '#6B6880', fontWeight: 500 }}>
            {f.label} ({f.n})
          </button>
        ))}
      </div>

      {/* lista */}
      <div style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 12, overflow: 'hidden' }}>
        {lista.map((r, i) => (
          <button key={r.id} onClick={() => setSel(r.id)} className="row-btn" style={{ display: 'flex', alignItems: 'center', gap: 14, width: '100%', textAlign: 'left', font: 'inherit', cursor: 'pointer', background: 'transparent', border: 'none', borderTop: i ? '1px solid #F0EEF6' : 'none', padding: '14px 18px' }}>
            <ExecBadge estado={r.estado} />
            <span style={{ fontFamily: 'ui-monospace,monospace', fontSize: 13, color: '#6B6880', width: 64 }}>{r.id}</span>
            <span style={{ fontSize: 13.5, color: '#1A1730', flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.entrada}</span>
            <span style={{ fontSize: 13, color: '#A09DB8', width: 150, textAlign: 'right' }}>{r.quando}</span>
            <span style={{ fontSize: 13, color: '#6B6880', width: 90, textAlign: 'right' }}>{r.dur}</span>
            <Icon name="chevronRight" size={16} color="#C9C3E0" />
          </button>
        ))}
      </div>
    </div>
  );
}

window.TabExecucoes = TabExecucoes;
