# dev.ps1 - Reinicio LIMPO do ambiente de desenvolvimento do Batuta (Windows).
#
# ASCII-ONLY de proposito: o Windows PowerShell 5.1 le .ps1 como ANSI (nao UTF-8);
# acentos/travessoes corrompem o parse. Mantenha este arquivo sem caracteres
# nao-ASCII.
#
# POR QUE existe: o `uvicorn --reload` no Windows usa multiprocessing (um processo
# "reloader" pai + um "worker" filho). O Windows NAO tem grupos de processo, entao
# quando o pai morre abruptamente (terminal fechado, processo de fundo morto), o
# worker-filho fica ORFAO e continua segurando o socket :8000 herdado - servindo
# CODIGO VELHO. Cada start empilha mais um orfao. `npx kill-port 8000` nao resolve:
# ele mira o "dono" da porta listado pelo SO (que pode ser o pai ja morto), e o
# worker orfao real continua vivo. Isso ja custou horas de "bug que nao existe no
# codigo". Ver memorias: feedback_qa-local-contaminado-deploy-limpo,
# feedback_reiniciar-servidores-no-qa.
#
# COMO resolve: (1) mata TODOS os processos do cerebro/interface por ASSINATURA de
# linha de comando (pega ate os orfaos de pai morto), nao so por porta; (2) sobe o
# cerebro SEM --reload (processo UNICO -> matar mata tudo, zero orfao); (3) loga em
# arquivo (inclui access log - da pra VER a requisicao chegando). Para "recarregar"
# apos mudar codigo do cerebro, rode este script de novo (leva ~2-3s).
#
# USO:
#   .\dev.ps1                # mata tudo, sobe cerebro (sem reload) + interface
#   .\dev.ps1 -SoReset       # so mata e libera as portas (nao sobe nada)
#   .\dev.ps1 -LimparCache   # tambem limpa .next e __pycache__ (se suspeitar de cache)

param(
  [switch]$SoReset,
  [switch]$LimparCache
)

$ErrorActionPreference = 'SilentlyContinue'
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path

function Porta-Livre($porta) {
  return -not (Get-NetTCPConnection -State Listen -LocalPort $porta -ErrorAction SilentlyContinue)
}

Write-Host "== 1) matando o CEREBRO (uvicorn + workers, inclui orfaos de pai morto) =="
$py = Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object { $_.CommandLine -match 'uvicorn' -or $_.CommandLine -match 'multiprocessing-fork' }
foreach ($p in $py) {
  Write-Host ("   PID {0}" -f $p.ProcessId)
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "== 2) matando a INTERFACE (next dev) =="
$nd = Get-CimInstance Win32_Process -Filter "name='node.exe'" |
  Where-Object { $_.CommandLine -match 'next' -or $_.CommandLine -match 'start-server' -or $_.CommandLine -match 'postcss' }
foreach ($p in $nd) {
  Write-Host ("   PID {0}" -f $p.ProcessId)
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "== 3) liberando :8000 e :3000 (donos remanescentes) =="
foreach ($porta in 8000, 3000) {
  Get-NetTCPConnection -State Listen -LocalPort $porta -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Milliseconds 800

if ((Porta-Livre 8000) -and (Porta-Livre 3000)) {
  Write-Host "   OK - :8000 e :3000 livres"
} else {
  Write-Host "   ATENCAO - ainda ocupadas:"
  Get-NetTCPConnection -State Listen -LocalPort 8000, 3000 -ErrorAction SilentlyContinue |
    Select-Object LocalPort, OwningProcess | Format-Table -AutoSize
}

if ($LimparCache) {
  Write-Host "== 3.5) limpando caches (.next + __pycache__) via npx rimraf =="
  Push-Location $raiz
  npx --yes rimraf "interface/.next" "cerebro/**/__pycache__" --glob
  Pop-Location
}

if ($SoReset) {
  Write-Host "== pronto (somente reset) =="
  return
}

Write-Host "== 4) subindo o CEREBRO em :8000 SEM --reload (deterministico) =="
$pyCerebro = Join-Path $raiz "cerebro\.venv\Scripts\python.exe"
$logCerebro = Join-Path $raiz "cerebro\.dev-cerebro.log"
$errCerebro = Join-Path $raiz "cerebro\.dev-cerebro.err.log"
Start-Process -FilePath $pyCerebro `
  -ArgumentList '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000' `
  -WorkingDirectory (Join-Path $raiz "cerebro") `
  -RedirectStandardOutput $logCerebro -RedirectStandardError $errCerebro `
  -WindowStyle Hidden
Write-Host "   requisicoes (access log): $logCerebro"
Write-Host "   startup/erros: $errCerebro"

Write-Host "== 5) subindo a INTERFACE em :3000 (next dev) =="
$logIface = Join-Path $raiz "interface\.dev-interface.log"
$errIface = Join-Path $raiz "interface\.dev-interface.err.log"
Start-Process -FilePath "npm.cmd" `
  -ArgumentList 'run', 'dev' `
  -WorkingDirectory (Join-Path $raiz "interface") `
  -RedirectStandardOutput $logIface -RedirectStandardError $errIface `
  -WindowStyle Hidden
Write-Host "   log da interface: $logIface"

Write-Host ""
Write-Host "Subindo... cerebro responde em ~2s, interface em ~5-10s (1a vez compila)."
Write-Host "Confira: http://127.0.0.1:8000/saude  e  http://localhost:3000"
Write-Host "Mudou codigo do cerebro? rode .\dev.ps1 de novo (sem --reload, e assim que recarrega)."
