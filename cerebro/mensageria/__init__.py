"""Camada de conversação (mensageria de mão dupla) — borda sobre o núcleo.

O canal é um INSTRUMENTO (`enviar_telegram`/`enviar_whatsapp`); aqui vive a
coordenação dos turnos: recebimento, roteamento, retoma, conversa/sessão. NÃO
toca o núcleo de orquestração (`orquestracao/cadeia.py`, `agente.py`) — só o usa.
Ver `docs/MENSAGERIA-PLANO.md`.
"""
