import type { ReactNode } from "react";

type ModalProps = {
  title: string;
  open: boolean;
  onClose: () => void;
  wide?: boolean;
  children: ReactNode;
};

export const Modal = ({ title, open, onClose, wide = false, children }: ModalProps) => {
  if (!open) {
    return null;
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <section className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <header className="modal-header">
          <strong>{title}</strong>
          <button className="ghost" onClick={onClose}>
            关闭
          </button>
        </header>
        <div className="modal-body">{children}</div>
      </section>
    </div>
  );
};
