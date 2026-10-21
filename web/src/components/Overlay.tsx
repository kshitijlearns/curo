'use client';
/** A bottom panel over everything (rendered at the page root, above the dock), Esc closes. */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

export function Overlay({
  labelledBy,
  onClose,
  children,
}: {
  labelledBy: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  if (!mounted) return null;
  return createPortal(
    <div className="overlay" role="dialog" aria-modal="true" aria-labelledby={labelledBy} onClick={onClose}>
      <div className="panel" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>,
    document.body,
  );
}
