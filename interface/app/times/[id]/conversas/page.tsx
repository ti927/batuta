import { Inbox } from "lucide-react";

// Pane direito quando nenhuma conversa está selecionada. A lista (esquerda) e as
// métricas vêm do layout (ConversasShell); aqui é só o convite a escolher uma.
export default function ConversasIndexPage() {
  return (
    <div className="flex h-full flex-1 flex-col items-center justify-center p-8 text-center">
      <Inbox className="size-8 text-muted-foreground/50" />
      <p className="mt-3 max-w-xs text-sm text-muted-foreground">
        Selecione uma conversa à esquerda para acompanhar, assumir o atendimento
        ou responder.
      </p>
    </div>
  );
}
