"use client";

import { motion, useReducedMotion } from "framer-motion";

// Animação de entrada `rise` (DESIGN-SYSTEM §13 / handoff §6.0): o conteúdo sobe
// 9px → 0 em 420ms. REGRA CRÍTICA: o repouso é sempre visível (opacity nunca é
// animada) e, com "reduzir movimento" ligado, não há animação alguma — o
// conteúdo nunca depende da animação para aparecer.
export function Rise({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const reduzir = useReducedMotion();
  if (reduzir) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ y: 9 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.42, ease: [0.2, 0.7, 0.3, 1], delay }}
    >
      {children}
    </motion.div>
  );
}
