import type { ReactNode } from 'react';

interface TerminalPaneProps {
  id: string;
  title: string;
  /** Right side of the header: small icon buttons. */
  actions?: ReactNode;
  /** Muted one-line status after the title. */
  status?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}

/** Shared frame for the activity and agent panes: mono header, scrolling body, optional footer. */
export function TerminalPane({ id, title, actions, status, footer, children }: TerminalPaneProps) {
  return <section className="terminal" aria-labelledby={`${id}-title`}>
    <header className="terminal-header"><h2 id={`${id}-title`}>{title}</h2>{status && <span className="terminal-status">{status}</span>}<div className="terminal-actions">{actions}</div></header>
    {children}
    {footer && <footer className="terminal-footer">{footer}</footer>}
  </section>;
}
