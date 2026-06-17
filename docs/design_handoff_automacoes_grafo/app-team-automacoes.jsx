// app-team-automacoes.jsx — Construtor de automação como GRAFO (estilo LangGraph).
// Substitui a aba linear de Automações. Nós arrastáveis, arestas condicionais
// rotuladas, loops e portão de aprovação. Painel lateral edita as saídas de cada
// nó — é onde a bifurcação ("se X vai pro agente Y, se Z vai pro agente 2") nasce.
const { useState: useStateA, useRef: useRefA, useEffect: useEffectA } = React;

// ---------- geometria ----------
const NODE_W = 234;
function autoNodeH(node) {
  if (node.tipo === 'gatilho') return 66;
  if (node.tipo === 'fim') return 56;
  if (node.tipo === 'roteador') return 74;
  return 90;
}
function autoAgent(ref) { return (window.CT.agentes || []).find(a => a.id === ref) || {}; }
function autoNodeName(node) {
  if (node.tipo === 'gatilho') return 'Gatilho';
  if (node.tipo === 'fim') return 'Fim';
  if (node.tipo === 'roteador') return node.nome || 'Roteador';
  return autoAgent(node.ref).nome || 'Agente';
}
function autoNodeColor(node) {
  if (node.tipo === 'agente') return autoAgent(node.ref).cor || '#B19CD9';
  return '#B19CD9';
}
// handle de saída i (de n) na borda direita
function autoHandleY(node, i, n) {
  const cy = node.y + autoNodeH(node) / 2;
  const span = (n - 1) * 17;
  return cy - span / 2 + i * 17;
}
const TONES = {
  ok:      { stroke: '#79C295', pillBg: '#E6F4EA', pillFg: '#2F7D45', pillBd: '#BEE3CB', dot: '#3DAA5C', label: 'aprova / segue' },
  loop:    { stroke: '#E3BB7C', pillBg: '#FDF1E3', pillFg: '#A9681A', pillBd: '#F0D9B4', dot: '#E89638', label: 'volta atrás' },
  normal:  { stroke: '#C3BFD6', pillBg: '#FFFFFF', pillFg: '#6B6880', pillBd: '#E3E0EE', dot: '#A09DB8', label: 'caminho normal' },
};
function autoTone(t) { return TONES[t] || TONES.normal; }

function autoEdges(nodes) {
  const map = {}; nodes.forEach(n => { map[n.id] = n; });
  const out = [];
  nodes.forEach(n => {
    const s = n.saidas || [];
    s.forEach((sa, i) => {
      const to = map[sa.destino];
      if (!to) return;
      out.push({ id: n.id + ':' + sa.id, from: n, to, sa, idx: i, count: s.length });
    });
  });
  return out;
}
function autoPath(e) {
  const sx = e.from.x + NODE_W, sy = autoHandleY(e.from, e.idx, e.count);
  const tx = e.to.x, ty = e.to.y + autoNodeH(e.to) / 2;
  const backward = tx < sx + 24;
  let c1x, c1y, c2x, c2y;
  if (!backward) {
    const dx = Math.max(64, (tx - sx) * 0.5);
    c1x = sx + dx; c1y = sy; c2x = tx - dx; c2y = ty;
  } else {
    const above = e.sa.lane === 'above';
    const depth = e.sa.lane === 'below2' ? 196 : 122;
    const laneY = above ? Math.min(sy, ty) - 124 : Math.max(sy, ty) + depth;
    c1x = sx + 84; c1y = laneY; c2x = tx - 84; c2y = laneY;
  }
  return { sx, sy, tx, ty, c1x, c1y, c2x, c2y, d: 'M ' + sx + ' ' + sy + ' C ' + c1x + ' ' + c1y + ' ' + c2x + ' ' + c2y + ' ' + tx + ' ' + ty };
}
function autoBez(p, t) {
  const mt = 1 - t;
  return {
    x: mt * mt * mt * p.sx + 3 * mt * mt * t * p.c1x + 3 * mt * t * t * p.c2x + t * t * t * p.tx,
    y: mt * mt * mt * p.sy + 3 * mt * mt * t * p.c1y + 3 * mt * t * t * p.c2y + t * t * t * p.ty,
  };
}
let _uid = 0; function autoUid() { return 's' + (Date.now() % 100000) + '_' + (_uid++); }

// ---------- estado inicial: o time real, agora com bifurcações ----------
function autoInitialGraph() {
  return [
    { id: 'gatilho', tipo: 'gatilho', x: 60, y: 238, gatilho: 'Manual', detalhe: 'Dispara pelo botão de teste, na tela da automação.',
      saidas: [{ id: 'g0', rotulo: 'inicia o fluxo', destino: 'cacador', tone: 'normal' }] },
    { id: 'cacador', tipo: 'agente', ref: 'cacador', x: 352, y: 226, inicial: true,
      saidas: [{ id: 'c0', rotulo: 'tema escolhido', destino: 'validador', tone: 'normal' }] },
    { id: 'validador', tipo: 'agente', ref: 'validador', x: 668, y: 226,
      saidas: [
        { id: 'v0', rotulo: 'pauta aprovada', destino: 'redator', tone: 'ok' },
        { id: 'v1', rotulo: 'pauta fraca · refazer', destino: 'cacador', tone: 'loop', lane: 'below' },
      ] },
    { id: 'redator', tipo: 'agente', ref: 'redator', x: 984, y: 226,
      saidas: [{ id: 'r0', rotulo: 'artigo escrito', destino: 'revisor', tone: 'normal' }] },
    { id: 'revisor', tipo: 'agente', ref: 'revisor', x: 1300, y: 226, gate: true,
      saidas: [
        { id: 'rv0', rotulo: 'aprovado', destino: 'publicador', tone: 'ok' },
        { id: 'rv1', rotulo: 'reprovado · ajustar', destino: 'redator', tone: 'loop', lane: 'above' },
      ] },
    { id: 'publicador', tipo: 'agente', ref: 'publicador', x: 1616, y: 226,
      saidas: [{ id: 'p0', rotulo: 'publicado', destino: 'fim', tone: 'ok' }] },
    { id: 'fim', tipo: 'fim', x: 1908, y: 240, saidas: [] },
  ];
}

// ---------- seta ----------
function AutoArrow({ p, color }) {
  const ang = Math.atan2(p.ty - p.c2y, p.tx - p.c2x) * 180 / Math.PI;
  return (
    <g transform={'translate(' + p.tx + ',' + p.ty + ') rotate(' + ang + ')'}>
      <path d="M 0 0 L -9 -4.4 L -6.2 0 L -9 4.4 Z" fill={color} />
    </g>
  );
}

// ---------- camada de arestas (SVG) ----------
function AutoEdgesLayer({ edges, selId, planeW, planeH }) {
  return (
    <svg width={planeW} height={planeH} style={{ position: 'absolute', top: 0, left: 0, overflow: 'visible', pointerEvents: 'none' }}>
      {edges.map(e => {
        const p = autoPath(e);
        const tn = autoTone(e.sa.tone);
        const active = selId === e.from.id;
        const stroke = active ? '#6D4AFF' : tn.stroke;
        return (
          <g key={e.id}>
            <path d={p.d} fill="none" stroke={stroke} strokeWidth={active ? 2.4 : 1.8} strokeLinecap="round" opacity={active ? 1 : 0.95} />
            <AutoArrow p={p} color={stroke} />
          </g>
        );
      })}
    </svg>
  );
}

// ---------- pílula-rótulo de cada aresta (HTML, na mesma transform) ----------
function AutoEdgeLabels({ edges, selId, onPick }) {
  return edges.map(e => {
    const p = autoPath(e);
    const m = autoBez(p, 0.5);
    const tn = autoTone(e.sa.tone);
    const active = selId === e.from.id;
    return (
      <button key={e.id + '-lbl'} onClick={(ev) => { ev.stopPropagation(); onPick(e.from.id); }}
        title="Editar esta saída"
        style={{ position: 'absolute', left: m.x, top: m.y, transform: 'translate(-50%,-50%)', cursor: 'pointer', font: 'inherit',
          display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap',
          background: tn.pillBg, color: tn.pillFg, border: '1px solid ' + (active ? '#6D4AFF' : tn.pillBd),
          borderRadius: 999, padding: '3px 10px', fontSize: 12, fontWeight: 500,
          boxShadow: active ? '0 0 0 3px rgba(109,74,255,.12)' : '0 1px 2px rgba(26,23,48,.05)' }}>
        {e.from.gate && e.sa.tone !== 'normal' && <Icon name="shield" size={12} color={tn.pillFg} />}
        {e.sa.tone === 'loop' && !e.from.gate && <span style={{ fontSize: 13, lineHeight: 1 }}>↺</span>}
        {e.sa.rotulo}
      </button>
    );
  });
}

// ---------- card de nó ----------
function AutoNode({ node, selected, onSelect, onDragStart }) {
  const h = autoNodeH(node);
  const n = (node.saidas || []).length;
  const isAgent = node.tipo === 'agente';
  const a = isAgent ? autoAgent(node.ref) : {};
  let bg = '#fff', bd = selected ? '#6D4AFF' : '#E8E6F0';

  const handles = (node.saidas || []).map((sa, i) => {
    const y = autoHandleY(node, i, n) - node.y;
    const tn = autoTone(sa.tone);
    return <span key={sa.id} title={sa.rotulo} style={{ position: 'absolute', right: -6, top: y - 5, width: 11, height: 11, borderRadius: 999, background: '#fff', border: '2px solid ' + tn.dot }} />;
  });

  let inner;
  if (node.tipo === 'gatilho') {
    inner = (
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '0 14px', height: '100%' }}>
        <span style={{ width: 34, height: 34, borderRadius: 9, background: '#6D4AFF', display: 'grid', placeItems: 'center', flex: 'none' }}><Icon name="zap" size={18} color="#fff" /></span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, color: '#A09DB8', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '.04em' }}>Gatilho</div>
          <div style={{ fontSize: 14.5, fontWeight: 500, color: '#1A1730' }}>{node.gatilho}</div>
        </div>
      </div>
    );
  } else if (node.tipo === 'fim') {
    bg = '#F4FAF6'; bd = selected ? '#6D4AFF' : '#CDE9D5';
    inner = (
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '0 16px', height: '100%' }}>
        <Icon name="checkCircle" size={20} color="#3DAA5C" />
        <div style={{ fontSize: 14.5, fontWeight: 500, color: '#2F7D45' }}>Fim · entrega ao usuário</div>
      </div>
    );
  } else if (node.tipo === 'roteador') {
    bg = '#FBFAFF'; bd = selected ? '#6D4AFF' : '#E0DAF6';
    inner = (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 14px', height: '100%' }}>
        <span style={{ width: 32, height: 32, borderRadius: 9, background: '#EFEAFF', display: 'grid', placeItems: 'center', flex: 'none' }}><Icon name="layers" size={17} color="#6D4AFF" /></span>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, color: '#9A8CCB', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '.04em' }}>Roteador</div>
          <div style={{ fontSize: 14, fontWeight: 500, color: '#1A1730', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{node.nome || 'Decisão'}</div>
        </div>
      </div>
    );
  } else {
    inner = (
      <div style={{ padding: '11px 13px', height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <RobotFace color={a.cor} size={28} lider={a.papel === 'lider'} />
          <span style={{ fontSize: 14, fontWeight: 500, color: '#1A1730', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{a.nome}</span>
          {node.inicial && <span style={{ fontSize: 10, color: '#3D2A99', background: '#EFEAFF', padding: '1px 6px', borderRadius: 999, fontWeight: 500, flex: 'none' }}>início</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: '#6B6880', display: 'inline-flex', alignItems: 'center', gap: 4 }}><Icon name="sparkles" size={11} color="#6D4AFF" /> {(a.modelo || '').replace('claude-', '')}</span>
          {(a.instrumentos || []).slice(0, 1).map((ins, k) => (
            <span key={k} style={{ fontSize: 10.5, color: '#6B6880', display: 'inline-flex', alignItems: 'center', gap: 3, background: '#FAFAF7', border: '1px solid #E8E6F0', padding: '1px 7px', borderRadius: 999 }}><Icon name={ins.icon} size={10} /> {ins.nome.split(' ')[0]}</span>
          ))}
          {node.gate && <span style={{ fontSize: 10.5, color: '#A9681A', display: 'inline-flex', alignItems: 'center', gap: 3, background: '#FDF1E3', border: '1px solid #F0D9B4', padding: '1px 7px', borderRadius: 999, fontWeight: 500 }}><Icon name="shield" size={10} /> espera você</span>}
        </div>
      </div>
    );
  }

  return (
    <div
      onMouseDown={(e) => onDragStart(e, node)}
      onClick={(e) => { e.stopPropagation(); onSelect(node.id); }}
      style={{ position: 'absolute', left: node.x, top: node.y, width: NODE_W, height: h,
        background: bg, border: '1px solid ' + bd, borderRadius: 12, cursor: 'grab',
        boxShadow: selected ? '0 0 0 3px rgba(109,74,255,.14)' : '0 1px 2px rgba(26,23,48,.05)',
        transition: 'box-shadow .12s, border-color .12s', userSelect: 'none' }}>
      {inner}
      {/* handle de entrada */}
      {node.tipo !== 'gatilho' && <span style={{ position: 'absolute', left: -6, top: h / 2 - 5, width: 11, height: 11, borderRadius: 999, background: '#fff', border: '2px solid #C3BFD6' }} />}
      {handles}
    </div>
  );
}

// ---------- inspector: editor de saídas (o coração da bifurcação) ----------
function AutoOutputRow({ node, sa, idx, nodes, onChange, onRemove }) {
  const tn = autoTone(sa.tone);
  const destinos = nodes.filter(n => n.id !== node.id && n.tipo !== 'gatilho');
  const toneKeys = ['normal', 'ok', 'loop'];
  return (
    <div style={{ border: '1px solid #E8E6F0', borderRadius: 10, padding: 11, background: '#FAFAF7', display: 'flex', flexDirection: 'column', gap: 9 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 9, height: 9, borderRadius: 999, background: tn.dot, flex: 'none' }} />
        <span style={{ fontSize: 11.5, color: '#A09DB8', fontWeight: 500 }}>Saída {idx + 1}</span>
        <div style={{ flex: 1 }} />
        <button onClick={() => onRemove(sa.id)} aria-label="Remover saída" style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#A09DB8', padding: 2 }}><Icon name="x" size={15} /></button>
      </div>
      <div>
        <label style={{ fontSize: 11, color: '#6B6880', display: 'block', marginBottom: 4 }}>{node.gate ? 'Decisão (o que você responde)' : 'Quando o resultado for…'}</label>
        <input value={sa.rotulo} onChange={(e) => onChange(sa.id, { rotulo: e.target.value })}
          style={{ width: '100%', border: '1px solid #E8E6F0', borderRadius: 7, padding: '7px 10px', fontSize: 13, fontFamily: 'inherit', color: '#1A1730', outline: 'none', background: '#fff' }} />
      </div>
      <div>
        <label style={{ fontSize: 11, color: '#6B6880', display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}><Icon name="arrowRight" size={12} color="#A09DB8" /> vai para</label>
        <select value={sa.destino} onChange={(e) => onChange(sa.id, { destino: e.target.value })}
          style={{ width: '100%', border: '1px solid #E8E6F0', borderRadius: 7, padding: '7px 10px', fontSize: 13, fontFamily: 'inherit', color: '#1A1730', outline: 'none', background: '#fff', cursor: 'pointer' }}>
          {destinos.map(d => <option key={d.id} value={d.id}>{autoNodeName(d)}{d.tipo === 'fim' ? '' : ''}</option>)}
        </select>
      </div>
      <div style={{ display: 'flex', gap: 5 }}>
        {toneKeys.map(tk => {
          const t = autoTone(tk); const on = sa.tone === tk;
          return (
            <button key={tk} onClick={() => onChange(sa.id, { tone: tk })} title={t.label}
              style={{ flex: 1, cursor: 'pointer', font: 'inherit', fontSize: 11, padding: '5px 4px', borderRadius: 7,
                border: '1px solid ' + (on ? t.dot : '#E8E6F0'), background: on ? t.pillBg : '#fff', color: on ? t.pillFg : '#A09DB8', fontWeight: on ? 500 : 400,
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
              <span style={{ width: 7, height: 7, borderRadius: 999, background: t.dot }} /> {t.label.split(' ')[0]}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function AutoInspector({ node, nodes, onPatch, onPatchSaida, onAddSaida, onRemoveSaida, onDelete }) {
  if (!node) {
    return (
      <div style={{ padding: '28px 22px', color: '#6B6880' }}>
        <div style={{ width: 42, height: 42, borderRadius: 11, background: '#EFEAFF', display: 'grid', placeItems: 'center', marginBottom: 12 }}><Icon name="layers" size={22} color="#6D4AFF" /></div>
        <div style={{ fontSize: 14.5, fontWeight: 500, color: '#1A1730', marginBottom: 6 }}>Selecione um nó</div>
        <p style={{ fontSize: 13, lineHeight: 1.55 }}>Clique em qualquer nó do grafo para editar suas saídas. É aqui que você cria as condicionais: cada saída tem um rótulo (“quando o resultado for X”) e um destino.</p>
        <div style={{ marginTop: 16, borderTop: '1px solid #E8E6F0', paddingTop: 14, display: 'flex', flexDirection: 'column', gap: 9 }}>
          {[['ok', 'Aprova / segue adiante'], ['loop', 'Volta atrás (refazer)'], ['normal', 'Caminho normal']].map(([k, t]) => {
            const tn = autoTone(k);
            return <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 9, fontSize: 12.5, color: '#6B6880' }}><span style={{ width: 22, height: 0, borderTop: '2.4px solid ' + tn.stroke }} /> {t}</div>;
          })}
        </div>
      </div>
    );
  }

  const isAgent = node.tipo === 'agente';
  const a = isAgent ? autoAgent(node.ref) : {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* cabeçalho do nó */}
      <div style={{ padding: '16px 18px', borderBottom: '1px solid #E8E6F0', display: 'flex', gap: 11, alignItems: 'flex-start' }}>
        {isAgent ? <RobotFace color={a.cor} size={38} lider={a.papel === 'lider'} />
          : <span style={{ width: 38, height: 38, borderRadius: 10, background: node.tipo === 'fim' ? '#E6F4EA' : '#EFEAFF', display: 'grid', placeItems: 'center', flex: 'none' }}><Icon name={node.tipo === 'gatilho' ? 'zap' : node.tipo === 'fim' ? 'checkCircle' : 'layers'} size={19} color={node.tipo === 'fim' ? '#3DAA5C' : '#6D4AFF'} /></span>}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 16, fontWeight: 500, color: '#1A1730' }}>{autoNodeName(node)}</div>
          <div style={{ fontSize: 12.5, color: '#6B6880', marginTop: 2 }}>{isAgent ? a.resumo : node.tipo === 'gatilho' ? 'O que inicia este fluxo' : node.tipo === 'fim' ? 'Entrega o resultado a quem pediu' : 'Decide o caminho da tarefa'}</div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 18px 30px' }}>
        {/* gatilho: escolha do tipo */}
        {node.tipo === 'gatilho' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 18 }}>
            {[['Manual', 'play', 'Dispara pelo botão de teste.'], ['Agendamento', 'clock', 'Roda sozinho num horário fixo.'], ['Webhook', 'zap', 'Um sistema externo dispara via URL.']].map(([k, ic, hint]) => {
              const on = node.gatilho === k;
              return (
                <button key={k} onClick={() => onPatch(node.id, { gatilho: k })} style={{ textAlign: 'left', cursor: 'pointer', font: 'inherit', display: 'flex', gap: 10, alignItems: 'flex-start', padding: 11, borderRadius: 9, border: '1px solid ' + (on ? '#6D4AFF' : '#E8E6F0'), background: on ? '#F4F1FE' : '#fff' }}>
                  <span style={{ width: 30, height: 30, borderRadius: 8, background: on ? '#6D4AFF' : '#EFEAFF', display: 'grid', placeItems: 'center', flex: 'none' }}><Icon name={ic} size={15} color={on ? '#fff' : '#6D4AFF'} /></span>
                  <div><div style={{ fontSize: 13.5, fontWeight: 500, color: '#1A1730' }}>{k}</div><div style={{ fontSize: 11.5, color: '#6B6880', marginTop: 1, lineHeight: 1.4 }}>{hint}</div></div>
                </button>
              );
            })}
          </div>
        )}

        {/* agente: gate toggle + abre editor */}
        {isAgent && (
          <div style={{ marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ background: '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 10, padding: '12px 13px', display: 'flex', gap: 11, alignItems: 'flex-start' }}>
              <Icon name="shield" size={17} color={node.gate ? '#E89638' : '#A09DB8'} style={{ marginTop: 1 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13.5, fontWeight: 500, color: '#1A1730' }}>Portão de aprovação</div>
                <div style={{ fontSize: 11.5, color: '#6B6880', marginTop: 2, lineHeight: 1.45 }}>O fluxo pausa aqui e espera você decidir. Sua resposta escolhe a saída.</div>
              </div>
              <button onClick={() => onPatch(node.id, { gate: !node.gate })} role="switch" aria-checked={node.gate} style={{ width: 40, height: 23, borderRadius: 999, border: 'none', cursor: 'pointer', background: node.gate ? '#6D4AFF' : '#D6D3E8', position: 'relative', flex: 'none', transition: 'background .15s' }}>
                <span style={{ position: 'absolute', top: 3, left: node.gate ? 20 : 3, width: 17, height: 17, borderRadius: 999, background: '#fff', transition: 'left .15s' }} />
              </button>
            </div>
          </div>
        )}

        {/* roteador: nome */}
        {node.tipo === 'roteador' && (
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 12, fontWeight: 500, color: '#6B6880', display: 'block', marginBottom: 6 }}>Nome da decisão</label>
            <input value={node.nome || ''} onChange={(e) => onPatch(node.id, { nome: e.target.value })} placeholder="ex.: É sobre agenda ou exame?"
              style={{ width: '100%', border: '1px solid #E8E6F0', borderRadius: 8, padding: '9px 11px', fontSize: 13.5, fontFamily: 'inherit', color: '#1A1730', outline: 'none' }} />
          </div>
        )}

        {/* saídas */}
        {node.tipo !== 'fim' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ fontSize: 12.5, fontWeight: 500, color: '#1A1730', display: 'inline-flex', alignItems: 'center', gap: 6 }}><Icon name="zap" size={14} color="#6D4AFF" /> Saídas {(node.saidas || []).length > 1 ? '· bifurca em ' + node.saidas.length : ''}</div>
              <div style={{ flex: 1 }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              {(node.saidas || []).map((sa, i) => (
                <AutoOutputRow key={sa.id} node={node} sa={sa} idx={i} nodes={nodes}
                  onChange={(sid, patch) => onPatchSaida(node.id, sid, patch)}
                  onRemove={(sid) => onRemoveSaida(node.id, sid)} />
              ))}
            </div>
            <button onClick={() => onAddSaida(node.id)} style={{ marginTop: 10, width: '100%', justifyContent: 'center', display: 'inline-flex', alignItems: 'center', gap: 7, background: '#F4F1FE', border: '1px dashed #C9B8FF', borderRadius: 9, padding: '9px', cursor: 'pointer', font: 'inherit', fontSize: 13, color: '#6D4AFF', fontWeight: 500 }}>
              <Icon name="plus" size={15} /> Adicionar saída (bifurcar)
            </button>
            {(node.saidas || []).length > 1 && (
              <p style={{ fontSize: 11.5, color: '#6B6880', marginTop: 9, lineHeight: 1.5, display: 'flex', gap: 6 }}><Icon name="circleHelp" size={13} color="#A09DB8" style={{ marginTop: 1, flex: 'none' }} /> {node.gate ? 'Sua resposta no portão escolhe por qual saída o fluxo segue.' : 'O agente classifica o resultado e segue por uma das saídas — é a aresta condicional do LangGraph.'}</p>
            )}
          </div>
        )}
        {node.tipo === 'fim' && <p style={{ fontSize: 13, color: '#6B6880', lineHeight: 1.55 }}>Quando a tarefa chega aqui, o líder entrega o resultado final a quem disparou o fluxo.</p>}
      </div>

      {/* rodapé */}
      {node.tipo !== 'gatilho' && node.tipo !== 'fim' && (
        <div style={{ padding: '12px 18px', borderTop: '1px solid #E8E6F0' }}>
          <button onClick={() => onDelete(node.id)} style={{ border: 'none', background: 'transparent', color: '#E5484D', cursor: 'pointer', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6, font: 'inherit' }}><Icon name="x" size={15} /> Remover nó</button>
        </div>
      )}
    </div>
  );
}

// ---------- TAB principal ----------
function TabAutomacoes({ onToast }) {
  const [nodes, setNodes] = useStateA(autoInitialGraph);
  const [selId, setSelId] = useStateA('validador');
  const [pan, setPan] = useStateA({ x: 30, y: -82 });
  const [zoom, setZoom] = useStateA(0.82);
  const [addOpen, setAddOpen] = useStateA(false);
  const vpRef = useRefA(null);
  const drag = useRefA(null);
  const panZoom = useRefA({ pan, zoom }); panZoom.current = { pan, zoom };

  const PLANE_W = 2400, PLANE_H = 1000;
  const edges = autoEdges(nodes);
  const sel = nodes.find(n => n.id === selId) || null;

  // patches
  const patchNode = (id, patch) => setNodes(ns => ns.map(n => n.id === id ? { ...n, ...patch } : n));
  const patchSaida = (id, sid, patch) => setNodes(ns => ns.map(n => n.id === id ? { ...n, saidas: n.saidas.map(s => s.id === sid ? { ...s, ...patch } : s) } : n));
  const addSaida = (id) => setNodes(ns => ns.map(n => {
    if (n.id !== id) return n;
    const dest = ns.find(x => x.id !== id && x.tipo !== 'gatilho');
    return { ...n, saidas: [...(n.saidas || []), { id: autoUid(), rotulo: 'nova condição', destino: dest ? dest.id : 'fim', tone: 'normal' }] };
  }));
  const removeSaida = (id, sid) => setNodes(ns => ns.map(n => n.id === id ? { ...n, saidas: n.saidas.filter(s => s.id !== sid) } : n));
  const deleteNode = (id) => {
    setNodes(ns => ns.filter(n => n.id !== id).map(n => ({ ...n, saidas: (n.saidas || []).filter(s => s.destino !== id) })));
    setSelId(null);
  };

  // adicionar nó no centro do viewport
  const addNode = (kind, ref) => {
    const vp = vpRef.current; const rect = vp ? vp.getBoundingClientRect() : { width: 800, height: 600 };
    const cx = (rect.width / 2 - panZoom.current.pan.x) / panZoom.current.zoom - NODE_W / 2;
    const cy = (rect.height / 2 - panZoom.current.pan.y) / panZoom.current.zoom - 45;
    const id = autoUid();
    let node;
    if (kind === 'roteador') node = { id, tipo: 'roteador', nome: 'Nova decisão', x: cx, y: cy, saidas: [{ id: autoUid(), rotulo: 'caso A', destino: 'fim', tone: 'normal' }] };
    else node = { id, tipo: 'agente', ref, x: cx, y: cy, saidas: [{ id: autoUid(), rotulo: 'resultado', destino: 'fim', tone: 'normal' }] };
    setNodes(ns => [...ns, node]);
    setSelId(id); setAddOpen(false);
    onToast && onToast(kind === 'roteador' ? 'Roteador adicionado' : 'Agente adicionado ao grafo');
  };

  // drag de nó / pan
  const onNodeDown = (e, node) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    drag.current = { mode: 'node', id: node.id, sx: e.clientX, sy: e.clientY, ox: node.x, oy: node.y, moved: false };
  };
  const onVpDown = (e) => {
    if (e.button !== 0) return;
    drag.current = { mode: 'pan', sx: e.clientX, sy: e.clientY, ox: pan.x, oy: pan.y, moved: false };
    setAddOpen(false);
  };
  useEffectA(() => {
    const move = (e) => {
      const d = drag.current; if (!d) return;
      const dx = e.clientX - d.sx, dy = e.clientY - d.sy;
      if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
      if (d.mode === 'node') {
        const z = panZoom.current.zoom;
        setNodes(ns => ns.map(n => n.id === d.id ? { ...n, x: d.ox + dx / z, y: d.oy + dy / z } : n));
      } else {
        setPan({ x: d.ox + dx, y: d.oy + dy });
      }
    };
    const up = () => {
      const d = drag.current;
      if (d && d.mode === 'pan' && !d.moved) setSelId(null);
      drag.current = null;
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
  }, []);

  // zoom na roda
  useEffectA(() => {
    const vp = vpRef.current; if (!vp) return;
    const onWheel = (e) => {
      e.preventDefault();
      const { pan: pp, zoom: zz } = panZoom.current;
      const rect = vp.getBoundingClientRect();
      const cx = e.clientX - rect.left, cy = e.clientY - rect.top;
      const nz = Math.min(1.5, Math.max(0.4, zz * (1 - e.deltaY * 0.0014)));
      const wx = (cx - pp.x) / zz, wy = (cy - pp.y) / zz;
      setZoom(nz); setPan({ x: cx - wx * nz, y: cy - wy * nz });
    };
    vp.addEventListener('wheel', onWheel, { passive: false });
    return () => vp.removeEventListener('wheel', onWheel);
  }, []);

  const zoomBy = (f) => {
    const vp = vpRef.current; const rect = vp.getBoundingClientRect();
    const cx = rect.width / 2, cy = rect.height / 2;
    const { pan: pp, zoom: zz } = panZoom.current;
    const nz = Math.min(1.5, Math.max(0.4, zz * f));
    const wx = (cx - pp.x) / zz, wy = (cy - pp.y) / zz;
    setZoom(nz); setPan({ x: cx - wx * nz, y: cy - wy * nz });
  };
  const fit = () => { setZoom(0.82); setPan({ x: 30, y: -82 }); };

  const agentes = window.CT.agentes || [];
  const branchCount = nodes.reduce((acc, n) => acc + ((n.saidas || []).length > 1 ? 1 : 0), 0);

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 24px', borderBottom: '1px solid #E8E6F0', background: '#fff', flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <h2 style={{ fontSize: 16, fontWeight: 500, color: '#1A1730' }}>{window.CT.automacao.nome}</h2>
            <span style={{ fontSize: 11.5, color: '#6B6880', background: '#FAFAF7', border: '1px solid #E8E6F0', padding: '2px 9px', borderRadius: 999, display: 'inline-flex', alignItems: 'center', gap: 5 }}><Icon name="layers" size={12} /> {nodes.filter(n => n.tipo === 'agente').length} agentes · {branchCount} bifurcações</span>
          </div>
          <p style={{ fontSize: 12.5, color: '#6B6880', marginTop: 3 }}>O caminho da tarefa, do gatilho à entrega — com condicionais e voltas.</p>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ position: 'relative' }}>
          <button className="btn-ghost" style={{ height: 36 }} onClick={() => setAddOpen(o => !o)}><Icon name="plus" size={15} color="#6D4AFF" /> Adicionar nó <Icon name="chevronDown" size={14} color="#A09DB8" /></button>
          {addOpen && (
            <div style={{ position: 'absolute', top: 42, right: 0, zIndex: 30, width: 240, background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, boxShadow: '0 12px 30px rgba(26,23,48,.12)', padding: 6 }}>
              <div style={{ fontSize: 11, color: '#A09DB8', fontWeight: 500, padding: '6px 8px 4px', textTransform: 'uppercase', letterSpacing: '.04em' }}>Agente do time</div>
              {agentes.map(a => (
                <button key={a.id} onClick={() => addNode('agente', a.id)} style={{ width: '100%', textAlign: 'left', cursor: 'pointer', font: 'inherit', display: 'flex', alignItems: 'center', gap: 9, padding: '7px 8px', borderRadius: 7, border: 'none', background: 'transparent', fontSize: 13, color: '#1A1730' }} className="row-btn">
                  <RobotFace color={a.cor} size={22} /> {a.nome}
                </button>
              ))}
              <div style={{ height: 1, background: '#E8E6F0', margin: '5px 4px' }} />
              <button onClick={() => addNode('roteador')} style={{ width: '100%', textAlign: 'left', cursor: 'pointer', font: 'inherit', display: 'flex', alignItems: 'center', gap: 9, padding: '7px 8px', borderRadius: 7, border: 'none', background: 'transparent', fontSize: 13, color: '#1A1730' }} className="row-btn">
                <span style={{ width: 22, height: 22, borderRadius: 6, background: '#EFEAFF', display: 'grid', placeItems: 'center' }}><Icon name="layers" size={13} color="#6D4AFF" /></span> Roteador / condição
              </button>
            </div>
          )}
        </div>
        <button className="btn-primary" style={{ height: 36 }} onClick={() => onToast && onToast('Automação salva')}><Icon name="check" size={15} /> Salvar</button>
      </div>

      {/* canvas + inspector */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <div ref={vpRef} onMouseDown={onVpDown}
          style={{ flex: 1, position: 'relative', overflow: 'hidden', cursor: drag.current && drag.current.mode === 'pan' ? 'grabbing' : 'default',
            background: '#FAFAF7', backgroundImage: 'radial-gradient(#E0DDF0 1.1px, transparent 1.1px)', backgroundSize: (22 * zoom) + 'px ' + (22 * zoom) + 'px', backgroundPosition: pan.x + 'px ' + pan.y + 'px' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: PLANE_W, height: PLANE_H, transform: 'translate(' + pan.x + 'px,' + pan.y + 'px) scale(' + zoom + ')', transformOrigin: '0 0' }}>
            <AutoEdgesLayer edges={edges} selId={selId} planeW={PLANE_W} planeH={PLANE_H} />
            <AutoEdgeLabels edges={edges} selId={selId} onPick={setSelId} />
            {nodes.map(n => <AutoNode key={n.id} node={n} selected={n.id === selId} onSelect={setSelId} onDragStart={onNodeDown} />)}
          </div>

          {/* controles de zoom */}
          <div style={{ position: 'absolute', bottom: 18, right: 18, display: 'flex', flexDirection: 'column', gap: 6, background: '#fff', border: '1px solid #E8E6F0', borderRadius: 10, padding: 5, boxShadow: '0 4px 14px rgba(26,23,48,.07)' }}>
            <button onClick={() => zoomBy(1.15)} aria-label="Aproximar" style={{ width: 30, height: 30, borderRadius: 7, border: 'none', background: 'transparent', cursor: 'pointer', color: '#1A1730', display: 'grid', placeItems: 'center' }} className="row-btn"><Icon name="plus" size={16} /></button>
            <div style={{ fontSize: 10.5, color: '#A09DB8', textAlign: 'center', fontWeight: 500 }}>{Math.round(zoom * 100)}%</div>
            <button onClick={() => zoomBy(1 / 1.15)} aria-label="Afastar" style={{ width: 30, height: 30, borderRadius: 7, border: 'none', background: 'transparent', cursor: 'pointer', color: '#1A1730', display: 'grid', placeItems: 'center' }} className="row-btn"><span style={{ width: 12, height: 2, background: '#1A1730', borderRadius: 2 }} /></button>
            <div style={{ height: 1, background: '#E8E6F0', margin: '1px 3px' }} />
            <button onClick={fit} aria-label="Enquadrar" style={{ width: 30, height: 30, borderRadius: 7, border: 'none', background: 'transparent', cursor: 'pointer', color: '#6B6880', display: 'grid', placeItems: 'center' }} className="row-btn"><Icon name="home" size={15} /></button>
          </div>

          {/* legenda */}
          <div style={{ position: 'absolute', bottom: 16, left: 16, background: 'rgba(255,255,255,.93)', border: '1px solid #E8E6F0', borderRadius: 10, padding: '9px 11px', backdropFilter: 'blur(4px)' }}>
            <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
              {[['ok', 'aprova / segue'], ['loop', '↺ volta atrás'], ['normal', 'normal']].map(([k, t]) => {
                const tn = autoTone(k);
                return <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: '#6B6880' }}><span style={{ width: 16, height: 0, borderTop: '2.4px solid ' + tn.stroke }} /> {t}</div>;
              })}
            </div>
            <div style={{ fontSize: 11, color: '#A09DB8', marginTop: 7, borderTop: '1px solid #EEEDF4', paddingTop: 6 }}>Arraste os nós · clique para editar · role para dar zoom</div>
          </div>
        </div>

        {/* inspector */}
        <div style={{ width: 348, flex: 'none', borderLeft: '1px solid #E8E6F0', background: '#fff', overflow: 'hidden' }}>
          <AutoInspector node={sel} nodes={nodes} onPatch={patchNode} onPatchSaida={patchSaida} onAddSaida={addSaida} onRemoveSaida={removeSaida} onDelete={deleteNode} />
        </div>
      </div>
    </div>
  );
}

window.TabAutomacoes = TabAutomacoes;
