import React from 'react';
import { useUIStore } from '../../store';
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react';
import './Toast.css';

const icons = {
  success: <CheckCircle size={16} />,
  error: <AlertCircle size={16} />,
  info: <Info size={16} />,
};

export default function ToastContainer() {
  const { toasts, removeToast } = useUIStore();
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          <span className="toast-icon">{icons[t.type] || icons.info}</span>
          <span className="toast-msg">{t.message}</span>
          <button className="toast-close" onClick={() => removeToast(t.id)}><X size={14} /></button>
        </div>
      ))}
    </div>
  );
}
