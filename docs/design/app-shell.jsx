// app-shell.jsx — Os três shells de navegação (A: sidebar, B: chat-hub, C: contexto do time)
const { useState: useStateSh } = React;
const useState = useStateSh;

const NAV_PRIMARY = [
  { icon: 'home', label: 'Início', key: 'placeholder:Início' },
  { icon: 'users', label: 'Times', teams: true },
  { icon: 'activity', label: 'Execuções', key: 'execucao' },
  { icon: 'library', label: 'Biblioteca', key: 'placeholder:Biblioteca' },
  { icon: 'gauge', label: 'Uso e custos', key: 'placeholder:Uso e custos' },
];
const NAV_ORG = [
  { icon: 'shield', label: 'Acesso e papéis', key: 'placeholder:Acesso e papéis' },
  { icon: 'key', label: 'Chaves de IA', key: 'placeholder:Chaves de IA' },
  { icon: 'settings', label: 'Configurações', key: 'placeholder:Configurações' },
];
const TEAMS = [
  { nome: 'Time de Blog SEO', key: 'dashboard' },
  { nome: 'Time Administrativo', key: 'placeholder:Time Administrativo' },
  { nome: 'Time de Atendimento', key: 'placeholder:Time de Atendimento' },
];

const CRUMBS = {
  criar: ['Times', 'Criar novo time'],
  dashboard: ['Times', 'Time de Blog SEO'],
  execucao: ['Time de Blog SEO', 'Execução #1284'],
  companheira: ['Time de Blog SEO', 'Conversar sobre o projeto'],
};

function Logo({ dark, size = 26 }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
      <img src="assets/simbolo.png" alt="" style={{ width: size, height: size, objectFit: 'contain' }} />
      <span style={{ fontFamily: "'Bricolage Grotesque',sans-serif", fontWeight: 600, fontSize: size * 0.78, letterSpacing: '-.01em', color: dark ? '#FAFAF7' : '#1A1730' }}>Batuta</span>
    </div>
  );
}

function ConsultorChip({ dark }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <span style={{ width: 32, height: 32, borderRadius: 999, background: 'linear-gradient(135deg,#6D4AFF,#B19CD9)', display: 'grid', placeItems: 'center', color: '#fff', fontSize: 13, fontWeight: 500, flex: 'none' }}>RM</span>
      <div style={{ lineHeight: 1.25, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: dark ? '#FAFAF7' : '#1A1730', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Rafael Maestro</div>
        <div style={{ fontSize: 11.5, color: dark ? '#9D9AB5' : '#6B6880' }}>Consultor · admin</div>
      </div>
    </div>
  );
}

function OrgSwitcher({ dark }) {
  return (
    <button className="org-switch" style={{
      display: 'flex', alignItems: 'center', gap: 9, width: '100%', cursor: 'pointer', font: 'inherit', textAlign: 'left',
      background: dark ? 'rgba(255,255,255,.06)' : '#fff', border: '1px solid ' + (dark ? 'rgba(255,255,255,.1)' : '#E8E6F0'),
      borderRadius: 9, padding: '8px 10px',
    }}>
      <span style={{ width: 26, height: 26, borderRadius: 7, background: '#3DD8C3', display: 'grid', placeItems: 'center', color: '#0c3b34', fontSize: 12, fontWeight: 600, flex: 'none' }}>CA</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: dark ? '#FAFAF7' : '#1A1730', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Clínica Aurora</div>
        <div style={{ fontSize: 11, color: dark ? '#9D9AB5' : '#6B6880' }}>Organização</div>
      </div>
      <Icon name="chevronDown" size={15} color={dark ? '#9D9AB5' : '#A09DB8'} />
    </button>
  );
}

// ============ A — SIDEBAR CLÁSSICA ============
function ShellSidebar({ children, screen, onNavigate }) {
  const [openTeams, setOpenTeams] = useState(true);
  const nav = onNavigate || (() => {});
  const itemBase = { display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', borderRadius: 8, fontSize: 14, cursor: 'pointer', color: '#C9C6DE', border: 'none', background: 'transparent', width: '100%', textAlign: 'left', font: 'inherit' };
  const isActive = (k) => k && k === screen;
  const crumb = CRUMBS[screen] || (typeof screen === 'string' && screen.startsWith('placeholder:') ? [screen.slice(12)] : ['Times']);
  return (
    <div style={{ display: 'flex', height: '100%', background: '#FAFAF7' }}>
      <aside style={{ width: 246, flex: 'none', background: '#1A1730', display: 'flex', flexDirection: 'column', padding: '18px 14px 14px' }}>
        <div style={{ padding: '0 6px 4px' }}><Logo dark /></div>
        <button className="btn-primary" onClick={() => nav('criar')} style={{ margin: '18px 4px 16px', justifyContent: 'flex-start', height: 40, boxShadow: isActive('criar') ? '0 0 0 3px rgba(109,74,255,.35)' : 'none' }}>
          <Icon name="sparkles" size={17} /> Criar com a IA
        </button>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {NAV_PRIMARY.map((it) => {
            const act = isActive(it.key);
            return (
            <div key={it.label}>
              <button className="nav-item" onClick={() => it.teams ? setOpenTeams(o => !o) : nav(it.key)} style={{ ...itemBase, color: act ? '#fff' : '#C9C6DE', background: act ? '#6D4AFF' : 'transparent' }}>
                <Icon name={it.icon} size={18} />
                <span style={{ flex: 1 }}>{it.label}</span>
                {it.teams && <Icon name="chevronDown" size={15} style={{ transform: openTeams ? 'none' : 'rotate(-90deg)', transition: 'transform .15s', opacity: .6 }} />}
              </button>
              {it.teams && openTeams && (
                <div style={{ margin: '2px 0 2px 27px', display: 'flex', flexDirection: 'column', gap: 1, borderLeft: '1px solid rgba(255,255,255,.1)', paddingLeft: 10 }}>
                  {TEAMS.map((t) => {
                    const tact = isActive(t.key) || (t.key === 'dashboard' && screen === 'companheira');
                    return (
                    <button key={t.nome} className="nav-sub" onClick={() => nav(t.key)} style={{ ...itemBase, padding: '7px 10px', fontSize: 13.5, color: tact ? '#fff' : '#9D9AB5', background: tact ? '#6D4AFF' : 'transparent' }}>
                      <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.nome}</span>
                    </button>
                  );})}
                </div>
              )}
            </div>
          );})}
        </nav>
        <div style={{ height: 1, background: 'rgba(255,255,255,.08)', margin: '14px 6px' }} />
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {NAV_ORG.map((it) => {
            const act = isActive(it.key);
            return <button key={it.label} className="nav-item" onClick={() => nav(it.key)} style={{ ...itemBase, color: act ? '#fff' : '#C9C6DE', background: act ? '#6D4AFF' : 'transparent' }}><Icon name={it.icon} size={18} /><span>{it.label}</span></button>;
          })}
        </nav>
        <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <OrgSwitcher dark />
          <div style={{ padding: '4px 6px' }}><ConsultorChip dark /></div>
        </div>
      </aside>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <header style={{ height: 56, flex: 'none', borderBottom: '1px solid #E8E6F0', background: '#fff', display: 'flex', alignItems: 'center', padding: '0 22px', gap: 8 }}>
          {crumb.map((c, i) => (
            <React.Fragment key={i}>
              {i > 0 && <Icon name="chevronRight" size={15} color="#D6D3E8" />}
              <span style={{ fontSize: i === crumb.length - 1 ? 14 : 13.5, fontWeight: i === crumb.length - 1 ? 500 : 400, color: i === crumb.length - 1 ? '#1A1730' : '#A09DB8' }}>{c}</span>
            </React.Fragment>
          ))}
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 12.5, color: '#6B6880', display: 'inline-flex', alignItems: 'center', gap: 6 }}><Icon name="circleHelp" size={15} /> Como funciona</span>
        </header>
        {children}
      </div>
    </div>
  );
}

// ============ B — CHAT COMO HUB ============
function ShellChatHub({ children }) {
  const rail = [{ icon: 'sparkles', active: true }, { icon: 'users' }, { icon: 'activity' }, { icon: 'library' }, { icon: 'gauge' }];
  return (
    <div style={{ display: 'flex', height: '100%', background: '#FAFAF7' }}>
      <aside style={{ width: 60, flex: 'none', background: '#1A1730', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '16px 0 14px', gap: 6 }}>
        <img src="assets/simbolo.png" alt="Batuta" style={{ width: 30, height: 30, objectFit: 'contain', marginBottom: 12 }} />
        {rail.map((r, i) => (
          <button key={i} className="rail-item" style={{ width: 40, height: 40, borderRadius: 10, border: 'none', cursor: 'pointer', background: r.active ? '#6D4AFF' : 'transparent', color: r.active ? '#fff' : '#9D9AB5', display: 'grid', placeItems: 'center' }}>
            <Icon name={r.icon} size={20} />
          </button>
        ))}
        <div style={{ marginTop: 'auto' }}>
          <span style={{ width: 34, height: 34, borderRadius: 999, background: 'linear-gradient(135deg,#6D4AFF,#B19CD9)', display: 'grid', placeItems: 'center', color: '#fff', fontSize: 13, fontWeight: 500 }}>RM</span>
        </div>
      </aside>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <header style={{ height: 56, flex: 'none', borderBottom: '1px solid #E8E6F0', background: '#fff', display: 'flex', alignItems: 'center', padding: '0 22px', gap: 14 }}>
          <span style={{ fontSize: 15, fontWeight: 500, color: '#1A1730', display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <Icon name="sparkles" size={17} color="#6D4AFF" /> Criar com a IA
          </span>
          <span style={{ fontSize: 12.5, color: '#6B6880', background: '#FAFAF7', border: '1px solid #E8E6F0', padding: '3px 10px', borderRadius: 999 }}>nova conversa</span>
          <div style={{ flex: 1 }} />
          <div style={{ width: 220 }}><OrgSwitcher /></div>
        </header>
        {children}
      </div>
    </div>
  );
}

// ============ C — CONTEXTO DO TIME ============
function ShellTeamContext({ children }) {
  const tabs = [{ label: 'Conversa', icon: 'sparkles', active: true }, { label: 'Agentes', icon: 'bot' }, { label: 'Cadeia', icon: 'layers' }, { label: 'Execuções', icon: 'activity' }, { label: 'Biblioteca', icon: 'library' }];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#FAFAF7' }}>
      <header style={{ height: 56, flex: 'none', borderBottom: '1px solid #E8E6F0', background: '#fff', display: 'flex', alignItems: 'center', padding: '0 22px', gap: 16 }}>
        <Logo size={24} />
        <div style={{ width: 1, height: 26, background: '#E8E6F0' }} />
        <button className="org-switch" style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', font: 'inherit', background: '#FAFAF7', border: '1px solid #E8E6F0', borderRadius: 9, padding: '6px 12px' }}>
          <span style={{ width: 22, height: 22, borderRadius: 6, background: '#3DD8C3', display: 'grid', placeItems: 'center', color: '#0c3b34', fontSize: 11, fontWeight: 600 }}>CA</span>
          <span style={{ fontSize: 13.5, color: '#6B6880' }}>Clínica Aurora</span>
          <Icon name="chevronRight" size={13} color="#A09DB8" />
          <span style={{ fontSize: 13.5, fontWeight: 500, color: '#1A1730' }}>Time de Blog SEO</span>
          <span style={{ fontSize: 10, fontWeight: 500, color: '#E89638', background: 'rgba(232,150,56,.14)', padding: '1px 7px', borderRadius: 999, marginLeft: 2 }}>rascunho</span>
          <Icon name="chevronDown" size={15} color="#A09DB8" style={{ marginLeft: 2 }} />
        </button>
        <div style={{ flex: 1 }} />
        <ConsultorChip />
      </header>
      <div style={{ height: 46, flex: 'none', borderBottom: '1px solid #E8E6F0', background: '#fff', display: 'flex', alignItems: 'stretch', padding: '0 18px', gap: 2 }}>
        {tabs.map((t) => (
          <button key={t.label} className="ctab" style={{
            display: 'inline-flex', alignItems: 'center', gap: 7, padding: '0 14px', cursor: 'pointer', font: 'inherit',
            border: 'none', background: 'transparent', fontSize: 13.5, fontWeight: 500,
            color: t.active ? '#6D4AFF' : '#6B6880', boxShadow: t.active ? 'inset 0 -2px 0 #6D4AFF' : 'none',
          }}>
            <Icon name={t.icon} size={16} /> {t.label}
          </button>
        ))}
      </div>
      {children}
    </div>
  );
}

window.ShellSidebar = ShellSidebar;
window.ShellChatHub = ShellChatHub;
window.ShellTeamContext = ShellTeamContext;
