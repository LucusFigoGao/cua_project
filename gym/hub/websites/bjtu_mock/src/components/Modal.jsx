import React, { useEffect } from 'react';

export default function Modal({ title, children, confirmText = '确定', cancelText = '取消', danger = false, onConfirm, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="overlay-mask" onClick={onClose} role="dialog" aria-modal="true" aria-label={title}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">{title}</div>
        <div className="modal-body">{children}</div>
        <div className="modal-actions">
          <button type="button" className="btn-ghost" onClick={onClose}>{cancelText}</button>
          <button type="button" className={danger ? 'btn-danger' : 'btn-primary'} onClick={onConfirm}>{confirmText}</button>
        </div>
      </div>
    </div>
  );
}
