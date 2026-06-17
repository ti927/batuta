// app-team.jsx — Workspace do time com ABAS. Sidebar real + container de abas + tabs Início/Agentes/Instrumentos/Automações.
const { useState: useStateT, useEffect: useEffectT } = React;

// ---------- Sidebar real (Lure Consultoria) ----------
function TeamSidebar({ teamActive }) {
  const [openTeams, setOpenTeams] = useStateT(true);
  const item = { display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', borderRadius: 8, fontSize: 14, cursor: 'pointer', color: '#C9C6DE', border: 'none', background: 'transparent', width: '100%', textAlign: 'left', font: 'inherit' };
  const prim = [
    { icon: 'home', label: 'Início' }, { icon: 'users', label: 'Times', teams: true },
    { icon: 'activity', label: 'Execuções' }, { icon: 'library', label: 'Biblioteca' }, { icon: 'gauge', label: 'Uso e custos' },
  ];
  const org = [
    { icon: 'shield', label: 'Acesso e papéis' }, { icon: 'key', label: 'Chaves e credenciais' },
    { icon: 'key', label: 'Chaves da consultoria' }, { icon: 'activity', label: 'Uso da consultoria' }, { icon: 'settings', label: 'Configurações' },
  ];
  return (
    <aside style={{ width: 246, flex: 'none', background: '#1A1730', display: 'flex', flexDirection: 'column', padding: '18px 14px 14px' }}>
      <div style={{ padding: '0 6px 4px', display: 'flex', alignItems: 'center', gap: 9 }}>
        <img src="assets/simbolo.png" alt="" style={{ width: 26, height: 26, objectFit: 'contain' }} />
        <span style={{ fontFamily: "'Bricolage Grotesque',sans-serif", fontWeight: 600, fontSize: 20, color: '#FAFAF7' }}>Batuta</span>
      </div>
      <button className="btn-primary" style={{ margin: '18px 4px 16px', justifyContent: 'center', height: 40 }}><Icon name="sparkles" size={17} /> Criar com a IA</button>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {prim.map((it) => (
          <div key={it.label}>
            <button className="nav-item" onClick={() => it.teams && setOpenTeams(o => !o)} style={item}>
              <Icon name={it.icon} size={18} /><span style={{ flex: 1 }}>{it.label}</span>
              {it.teams && <Icon name="chevronDown" size={15} style={{ transform: openTeams ? 'none' : 'rotate(-90deg)', transition: 'transform .15s', opacity: .6 }} />}
            </button>
            {it.teams && openTeams && (
              <div style={{ margin: '2px 0 2px 27px', display: 'flex', flexDirection: 'column', gap: 1, borderLeft: '1px solid rgba(255,255,255,.1)', paddingLeft: 10 }}>
                {window.TEAMS_SIDEBAR.map((t) => {
                  const act = t.key === 'time' && teamActive;
                  return <button key={t.nome} className="nav-sub" style={{ ...item, padding: '7px 10px', fontSize: 13.5, color: act ? '#fff' : '#9D9AB5', background: act ? '#6D4AFF' : 'transparent' }}>
                    <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.nome}</span>
                  </button>;
                })}
              </div>
            )}
          </div>
        ))}
      </nav>
      <div style={{ height: 1, background: 'rgba(255,255,255,.08)', margin: '14px 6px' }} />
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {org.map((it) => <button key={it.label} className="nav-item" style={item}><Icon name={it.icon} size={18} /><span>{it.label}</span></button>)}
      </nav>
      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <button className="org-switch" style={{ display: 'flex', alignItems: 'center', gap: 9, width: '100%', cursor: 'pointer', font: 'inherit', textAlign: 'left', background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 9, padding: '8px 10px' }}>
          <span style={{ width: 26, height: 26, borderRadius: 7, background: 'linear-gradient(135deg,#3DD8C3,#F5C44A)', display: 'grid', placeItems: 'center', flex: 'none' }}>
            <span style={{ width: 14, height: 14, borderRadius: 4, background: '#fff', opacity: .9 }} />
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: '#FAFAF7', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{window.ORG.nome}</div>
          </div>
          <Icon name="chevronDown" size={15} color="#9D9AB5" />
        </button>
        <div style={{ padding: '4px 6px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 30, height: 30, borderRadius: 999, background: 'linear-gradient(135deg,#6D4AFF,#B19CD9)', display: 'grid', placeItems: 'center', color: '#fff', fontSize: 13, fontWeight: 500, flex: 'none' }}>{window.USER.inicial}</span>
          <div style={{ fontSize: 12.5, color: '#9D9AB5', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>{window.USER.nome}</div>
          <Icon name="arrowRight" size={15} color="#6B6880" style={{ transform: 'rotate(0deg)' }} />
        </div>
      </div>
    </aside>
  );
}

// ---------- Cadeia horizontal (lê CT) ----------
function CadeiaCT({ compact }) {
  const T = window.CT;
  const chip = (children) => <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#fff', border: '1px solid #E8E6F0', borderRadius: 9, padding: compact ? '7px 10px' : '8px 11px', whiteSpace: 'nowrap' }}>{children}</div>;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      {window.CT_CADEIA.map((n, i) => {
        let inner;
        if (n.tipo === 'gatilho') inner = chip(<><span style={{ width: 22, height: 22, borderRadius: 6, background: '#EFEAFF', display: 'grid', placeItems: 'center' }}><Icon name="zap" size={13} color="#6D4AFF" /></span><span style={{ fontSize: 13, fontWeight: 500 }}>Gatilho</span></>);
        else if (n.tipo === 'agente') { const a = T.agentes.find(x => x.id === n.ref); inner = chip(<><RobotFace color={a.cor} size={22} /><span style={{ fontSize: 13, fontWeight: 500 }}>{a.nome}</span></>); }
        else if (n.tipo === 'portao') inner = chip(<><span style={{ width: 22, height: 22, borderRadius: 6, background: '#FDF1E3', display: 'grid', placeItems: 'center' }}><Icon name="message" size={13} color="#E89638" /></span><span style={{ fontSize: 13, fontWeight: 500, color: '#E89638' }}>{n.label}</span></>);
        else inner = chip(<><span style={{ width: 22, height: 22, borderRadius: 6, background: '#E6F4EA', display: 'grid', placeItems: 'center' }}><Icon name="checkCircle" size={13} color="#3DAA5C" /></span><span style={{ fontSize: 13, fontWeight: 500 }}>Fim</span></>);
        return <React.Fragment key={i}>{inner}{i < window.CT_CADEIA.length - 1 && <Icon name="chevronRight" size={15} color="#C9C3E0" />}</React.Fragment>;
      })}
    </div>
  );
}

// ---------- Aba: Início ----------
function StatBox({ icon, tone, label, value, sub, accent, onClick }) {
  const [h, setH] = useStateT(false);
  return (
    <div onClick={onClick} onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{ background: '#fff', border: '1px solid ' + (accent ? '#F0D9B8' : (h && onClick ? '#D6D3E8' : '#E8E6F0')), borderRadius: 12, padding: 18, flex: 1, minWidth: 180, cursor: onClick ? 'pointer' : 'default', transition: 'border-color .15s, transform .15s', transform: h && onClick ? 'translateY(-1px)' : 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 12 }}>
        <span style={{ width: 30, height: 30, borderRadius: 8, background: tone.bg, display: 'grid', placeItems: 'center' }}><Icon name={icon} size={16} color={tone.fg} /></span>
        <span style={{ fontSize: 12.5, color: '#6B6880' }}>{label}</span>
        {onClick && <Icon name="chevronRight" size={15} color="#C9C3E0" style={{ marginLeft: 'auto' }} />}
      </div>
      <div style={{ fontSize: 23, fontWeight: 500, color: '#1A1730', fontFamily: "'Bricolage Grotesque',sans-serif", lineHeight: 1.15 }}>{value}</div>
      <div style={{ fontSize: 12, color: accent ? '#E89638' : '#6B6880', marginTop: 4 }}>{sub}</div>
    </div>
  );
}

function TabInicio({ go, onAgent }) {
  const T = window.CT;
  const runsConcl = window.CT_RUNS.filter(r => r.estado === 'concluida').length;
  const pend = window.CT_RUNS.filter(r => r.estado === 'aguardando_humano').length;
  return (
    <div style={{ padding: '24px 0 60px' }}>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        <StatBox icon="zap" tone={{ bg: '#EFEAFF', fg: '#6D4AFF' }} label="Gatilho" value="Manual" sub="disparo pelo botão de teste" />
        <StatBox icon="message" tone={{ bg: pend ? '#FDF1E3' : '#E6F4EA', fg: pend ? '#E89638' : '#3DAA5C' }} label="Aguardando você" value={pend ? pend + ' pendente' : 'Nada pendente'} sub={pend ? 'uma execução parou pra você →' : 'nenhum fluxo parado'} accent={!!pend} onClick={() => go('execucoes')} />
        <StatBox icon="gauge" tone={{ bg: '#E6F4EA', fg: '#3DAA5C' }} label="Custo acumulado" value="~US$ 0.74" sub={window.CT_RUNS.length + ' execuções · estimado'} />
        <StatBox icon="checkCircle" tone={{ bg: '#EFEAFF', fg: '#6D4AFF' }} label="Taxa de sucesso" value="67%" sub={runsConcl + ' de ' + window.CT_RUNS.length + ' concluídas'} />
      </div>

      <SectionLabel icon="layers">Cadeia · o caminho da tarefa</SectionLabel>
      <div style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 12, padding: 18 }}>
        <CadeiaCT />
        <button onClick={() => go('automacoes')} className="link-roxo" style={{ marginTop: 14, display: 'inline-flex', alignItems: 'center', gap: 5, background: 'transparent', border: 'none', cursor: 'pointer', font: 'inherit', fontSize: 13, color: '#6D4AFF', padding: 0 }}>
          <Icon name="pencil" size={14} /> Editar a automação
        </button>
      </div>

      <SectionLabel icon="activity">Execuções recentes</SectionLabel>
      <div style={{ background: '#fff', border: '1px solid #E8E6F0', borderRadius: 12, overflow: 'hidden' }}>
        {window.CT_RUNS.slice(0, 3).map((r, i) => (
          <button key={r.id} onClick={() => go('execucoes', r.id)} className="row-btn" style={{ display: 'flex', alignItems: 'center', gap: 14, width: '100%', textAlign: 'left', font: 'inherit', cursor: 'pointer', background: 'transparent', border: 'none', borderTop: i ? '1px solid #F0EEF6' : 'none', padding: '13px 18px' }}>
            <ExecBadge estado={r.estado} />
            <span style={{ fontFamily: 'ui-monospace,monospace', fontSize: 13, color: '#6B6880' }}>{r.id}</span>
            <span style={{ fontSize: 13.5, color: '#1A1730' }}>{r.entrada}</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 13, color: '#A09DB8' }}>{r.quando}</span>
            <Icon name="chevronRight" size={16} color="#C9C3E0" />
          </button>
        ))}
      </div>

      <SectionLabel icon="bot" count={T.agentes.length}>Agentes</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {T.agentes.map(a => <AgentCardCT key={a.id} a={a} onClick={() => onAgent(a)} />)}
      </div>
    </div>
  );
}

// ---------- Card de agente (variante team, com badge ativo) ----------
function AgentCardCT({ a, onClick }) {
  const [h, setH] = useStateT(false);
  return (
    <button onClick={onClick} onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{ textAlign: 'left', cursor: 'pointer', font: 'inherit', width: '100%', background: '#fff', border: '1px solid ' + (h ? '#D6D3E8' : '#E8E6F0'), borderRadius: 10, padding: 14, display: 'flex', gap: 12, alignItems: 'flex-start', transition: 'border-color .15s, transform .15s, box-shadow .15s', transform: h ? 'translateY(-1px)' : 'none', boxShadow: h ? '0 4px 16px rgba(109,74,255,.08)' : 'none' }}>
      <RobotFace color={a.cor} size={40} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 500, fontSize: 15 }}>{a.nome}</span>
          {a.papel === 'inicial' && <span style={{ fontSize: 11, color: '#3D2A99', background: '#EFEAFF', padding: '1px 7px', borderRadius: 999, fontWeight: 500 }}>inicial</span>}
          {a.gate && <span style={{ fontSize: 11, color: '#E89638', background: '#FDF1E3', padding: '1px 7px', borderRadius: 999, fontWeight: 500 }}>portão</span>}
        </div>
        <div style={{ fontSize: 13, color: '#6B6880', marginTop: 3, lineHeight: 1.45, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{a.resumo}</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 9, alignItems: 'center' }}>
          <span style={{ fontSize: 11.5, color: '#6B6880', display: 'inline-flex', alignItems: 'center', gap: 4 }}><Icon name="sparkles" size={12} color="#6D4AFF" /> {a.modelo}</span>
          {a.instrumentos.map((i, k) => <span key={k} style={{ fontSize: 11.5, color: '#6B6880', display: 'inline-flex', alignItems: 'center', gap: 4, background: '#FAFAF7', border: '1px solid #E8E6F0', padding: '2px 8px', borderRadius: 999 }}><Icon name={i.icon} size={12} /> {i.nome}</span>)}
        </div>
      </div>
      <Icon name="pencil" size={15} color="#A09DB8" style={{ marginTop: 2 }} />
    </button>
  );
}

// ---------- Aba: Agentes ----------
function TabAgentes({ onAgent }) {
  const T = window.CT;
  return (
    <div style={{ padding: '24px 0 60px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
        <div><h2 style={{ fontSize: 17, fontWeight: 500 }}>Agentes do time</h2><p style={{ fontSize: 13.5, color: '#6B6880', marginTop: 3 }}>Cada agente é um especialista. Clique para editar quem ele é, o que sabe e seu cinto.</p></div>
        <div style={{ flex: 1 }} />
        <button className="btn-primary" style={{ height: 38 }}><Icon name="plus" size={16} /> Novo agente</button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 16 }}>
        {T.agentes.map(a => <AgentCardCT key={a.id} a={a} onClick={() => onAgent(a)} />)}
      </div>
    </div>
  );
}

// ---------- Aba: Instrumentos ----------
function TabInstrumentos({ onInstr }) {
  const T = window.CT;
  return (
    <div style={{ padding: '24px 0 60px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
        <div><h2 style={{ fontSize: 17, fontWeight: 500 }}>Instrumentos do time</h2><p style={{ fontSize: 13.5, color: '#6B6880', marginTop: 3 }}>As ferramentas que os agentes podem usar. Um instrumento pode exigir sua aprovação antes de agir.</p></div>
        <div style={{ flex: 1 }} />
        <button className="btn-primary" style={{ height: 38 }}><Icon name="plus" size={16} /> Novo instrumento</button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {T.instrumentos.map(inst => (
          <button key={inst.id} onClick={() => onInstr(inst)} className="row-btn" style={{ display: 'flex', alignItems: 'center', gap: 13, width: '100%', textAlign: 'left', font: 'inherit', cursor: 'pointer', background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, padding: '14px 16px' }}>
            <span style={{ width: 38, height: 38, borderRadius: 9, background: '#EFEAFF', display: 'grid', placeItems: 'center', flex: 'none' }}><Icon name={inst.icon} size={19} color="#6D4AFF" /></span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 14.5, fontWeight: 500 }}>{inst.nome}</span>
                {inst.exigeAprovacao && <span style={{ fontSize: 11, fontWeight: 500, color: '#E89638', background: '#FDF1E3', padding: '2px 8px', borderRadius: 999, display: 'inline-flex', alignItems: 'center', gap: 4 }}><Icon name="shield" size={12} /> exige aprovação</span>}
              </div>
              <div style={{ fontSize: 12.5, color: '#6B6880', marginTop: 3, display: 'flex', gap: 10, alignItems: 'center' }}>
                <span style={{ fontFamily: 'ui-monospace,monospace' }}>{inst.slug}</span>
                <span>· usado por {inst.usadoPor.join(', ')}</span>
              </div>
            </div>
            <Icon name="pencil" size={16} color="#A09DB8" />
          </button>
        ))}
      </div>
    </div>
  );
}

window.TeamSidebar = TeamSidebar;
window.CadeiaCT = CadeiaCT;
window.TabInicio = TabInicio;
window.TabAgentes = TabAgentes;
window.TabInstrumentos = TabInstrumentos;
window.AgentCardCT = AgentCardCT;
