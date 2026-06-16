// app-team-convos.jsx — Aba Conversas (master-detail two-pane: lista + thread)
const { useState: useStateC } = React;

function ConvStat({ label, value, sub }) {
  return (
    <div style={{ flex: 1, minWidth: 130, background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, padding: 14 }}>
      <div style={{ fontSize: 12, color: '#6B6880' }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 500, fontFamily: "'Bricolage Grotesque',sans-serif", marginTop: 4 }}>{value}</div>
      {sub && <div style={{ fontSize: 11.5, color: '#A09DB8', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function ConvAvatar({ nome, size = 38 }) {
  const ini = nome.split(' ').map(w => w[0]).slice(0, 2).join('');
  return <span style={{ width: size, height: size, borderRadius: 999, background: 'linear-gradient(135deg,#B19CD9,#6D4AFF)', display: 'grid', placeItems: 'center', color: '#fff', fontSize: size * 0.34, fontWeight: 500, flex: 'none' }}>{ini}</span>;
}

function ConvBadge({ estado, humano }) {
  if (humano) return <span style={{ fontSize: 11, fontWeight: 500, color: '#E89638', background: '#FDF1E3', padding: '2px 9px', borderRadius: 999, display: 'inline-flex', alignItems: 'center', gap: 4 }}><Icon name="users" size={11} /> com humano</span>;
  const map = { fechada: { fg: '#6B6880', bg: '#F0EEF6', l: 'Fechada' }, andamento: { fg: '#6D4AFF', bg: '#EFEAFF', l: 'Em andamento' } };
  const s = map[estado] || map.fechada;
  return <span style={{ fontSize: 11, fontWeight: 500, color: s.fg, background: s.bg, padding: '2px 9px', borderRadius: 999 }}>{s.l}</span>;
}

function ConvThread({ conv, onAssumir, onToast }) {
  const T = window.CT;
  const bubbles = conv.thread && conv.thread.length ? conv.thread : null;
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: '#fff' }}>
      <div style={{ padding: '14px 20px', borderBottom: '1px solid #E8E6F0', display: 'flex', alignItems: 'center', gap: 12 }}>
        <ConvAvatar nome={conv.contato} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 500 }}>{conv.contato}</div>
          <div style={{ fontSize: 12, color: '#6B6880', display: 'inline-flex', alignItems: 'center', gap: 6 }}><Icon name="message" size={12} /> {conv.canal} · {conv.turnos} turnos</div>
        </div>
        <ConvBadge estado={conv.estado} humano={conv.humano} />
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 12, background: '#FBFAFE' }}>
        {bubbles ? bubbles.map((m, i) => {
          if (m.de === 'sistema') return <div key={i} style={{ alignSelf: 'center', fontSize: 12, color: '#A09DB8', background: '#F0EEF6', padding: '5px 12px', borderRadius: 999, display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name="users" size={12} /> {m.txt}</div>;
          const isContato = m.de === 'contato';
          return (
            <div key={i} style={{ alignSelf: isContato ? 'flex-start' : 'flex-end', maxWidth: '78%' }}>
              <div style={isContato
                ? { background: '#fff', border: '1px solid #E8E6F0', color: '#1A1730', borderRadius: '4px 14px 14px 14px', padding: '10px 13px', fontSize: 13.5, lineHeight: 1.5 }
                : { background: '#EFEAFF', color: '#2A2150', borderRadius: '14px 14px 4px 14px', padding: '10px 13px', fontSize: 13.5, lineHeight: 1.5 }}>
                {m.txt}
              </div>
              <div style={{ fontSize: 10.5, color: '#A09DB8', marginTop: 3, textAlign: isContato ? 'left' : 'right', display: 'flex', gap: 5, alignItems: 'center', justifyContent: isContato ? 'flex-start' : 'flex-end' }}>
                {!isContato && <Icon name="sparkles" size={10} color="#6D4AFF" />}{!isContato ? 'IA do time' : conv.contato} · {m.hora}
              </div>
            </div>
          );
        }) : (
          <div style={{ margin: 'auto', textAlign: 'center', color: '#A09DB8' }}>
            <Icon name="message" size={32} color="#D6D3E8" style={{ margin: '0 auto 10px' }} />
            <div style={{ fontSize: 13.5 }}>Transcrição completa disponível ao abrir.</div>
            <div style={{ fontSize: 12.5, marginTop: 4 }}>{conv.turnos} turnos · {conv.canal}</div>
          </div>
        )}
      </div>
      <div style={{ padding: '12px 20px', borderTop: '1px solid #E8E6F0', display: 'flex', gap: 10, alignItems: 'center' }}>
        {conv.estado === 'fechada' ? (
          <div style={{ fontSize: 12.5, color: '#A09DB8', display: 'flex', alignItems: 'center', gap: 6 }}><Icon name="checkCircle" size={14} /> Conversa encerrada · {conv.quando}</div>
        ) : (
          <>
            <input placeholder="Responder como humano…" style={{ flex: 1, border: '1px solid #E8E6F0', borderRadius: 9, padding: '9px 13px', fontSize: 13.5, fontFamily: 'inherit', outline: 'none', background: '#FAFAF7' }} />
            <button className="btn-primary" style={{ width: 38, height: 38, padding: 0 }}><Icon name="send" size={16} /></button>
          </>
        )}
        <div style={{ flex: 1 }} />
        <button onClick={() => onToast('Você assumiu a conversa')} className="btn-ghost" style={{ height: 36 }}><Icon name="users" size={14} /> Assumir atendimento</button>
      </div>
    </div>
  );
}

function TabConversas({ onToast }) {
  const S = window.CT_CONVERSAS_STATS;
  const convs = window.CT_CONVERSAS;
  const [filtro, setFiltro] = useStateC('todas');
  const [sel, setSel] = useStateC(convs[0].id);
  const filtros = [
    { key: 'andamento', label: 'Em andamento', n: convs.filter(c => c.estado === 'andamento').length },
    { key: 'humano', label: 'Com humano', n: convs.filter(c => c.humano).length },
    { key: 'fechada', label: 'Fechadas', n: convs.filter(c => c.estado === 'fechada').length },
    { key: 'todas', label: 'Todas', n: convs.length },
  ];
  const lista = filtro === 'todas' ? convs : filtro === 'humano' ? convs.filter(c => c.humano) : convs.filter(c => c.estado === filtro);
  const selConv = convs.find(c => c.id === sel) || lista[0];

  return (
    <div style={{ padding: '24px 0 24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ marginBottom: 14 }}>
        <h2 style={{ fontSize: 17, fontWeight: 500 }}>Conversas</h2>
        <p style={{ fontSize: 13.5, color: '#6B6880', marginTop: 3 }}>As conversas dos canais deste time. Abra uma para acompanhar, assumir o atendimento ou responder.</p>
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        <ConvStat label="Conversas" value={S.total} sub="últimos 30 dias" />
        <ConvStat label="Em andamento" value={S.andamento} />
        <ConvStat label="Foram p/ humano" value={S.humano} sub={S.humanoPct} />
        <ConvStat label="1ª resposta (média)" value={S.primeira} />
        <ConvStat label="Custo de IA" value={S.custo} />
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
        {filtros.map(f => (
          <button key={f.key} onClick={() => setFiltro(f.key)} style={{ cursor: 'pointer', font: 'inherit', fontSize: 13, padding: '7px 14px', borderRadius: 999, border: '1px solid ' + (filtro === f.key ? '#6D4AFF' : '#E8E6F0'), background: filtro === f.key ? '#6D4AFF' : '#fff', color: filtro === f.key ? '#fff' : '#6B6880', fontWeight: 500 }}>{f.label} ({f.n})</button>
        ))}
      </div>

      {/* two-pane */}
      <div style={{ flex: 1, minHeight: 420, display: 'flex', border: '1px solid #E8E6F0', borderRadius: 12, overflow: 'hidden', background: '#fff' }}>
        <div style={{ width: 320, flex: 'none', borderRight: '1px solid #E8E6F0', overflowY: 'auto' }}>
          {lista.map((c) => {
            const active = selConv && c.id === selConv.id;
            return (
              <button key={c.id} onClick={() => setSel(c.id)} style={{ display: 'flex', gap: 11, width: '100%', textAlign: 'left', font: 'inherit', cursor: 'pointer', border: 'none', borderBottom: '1px solid #F0EEF6', background: active ? '#F4F1FE' : 'transparent', padding: '13px 15px', borderLeft: '2px solid ' + (active ? '#6D4AFF' : 'transparent') }}>
                <ConvAvatar nome={c.contato} size={34} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 13.5, fontWeight: 500, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.contato}</span>
                    <ConvBadge estado={c.estado} humano={c.humano} />
                  </div>
                  <div style={{ fontSize: 11.5, color: '#A09DB8', marginTop: 3 }}>{c.turnos} turnos · {c.quando}</div>
                </div>
              </button>
            );
          })}
        </div>
        {selConv ? <ConvThread conv={selConv} onToast={onToast} /> : <div style={{ flex: 1, display: 'grid', placeItems: 'center', color: '#A09DB8', fontSize: 13.5 }}>Selecione uma conversa</div>}
      </div>
    </div>
  );
}

window.TabConversas = TabConversas;
