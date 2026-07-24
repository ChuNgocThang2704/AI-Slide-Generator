import { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../../store';
import { subscriptionService } from '../../services/subscriptionService';
import './PaymentResultPage.css';

export default function PaymentResultPage({ cancelled = false }) {
  const { updateUser } = useAuthStore();
  const [checking, setChecking] = useState(!cancelled);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (cancelled) return undefined;
    let disposed = false;
    const verify = async () => {
      for (let attempt = 0; attempt < 6 && !disposed; attempt += 1) {
        try {
          const subscription = await subscriptionService.getMySubscription();
          const code = String(subscription?.packageCode || subscription?.package?.code || '').toLowerCase();
          if (code) {
            updateUser({ plan: code });
            setConfirmed(true);
            break;
          }
        } catch {
          // Payment webhook may still be processing.
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
      }
      if (!disposed) setChecking(false);
    };
    verify();
    return () => { disposed = true; };
  }, [cancelled, updateUser]);

  return (
    <main className="payment-result-page page-enter">
      <div className="payment-result-panel">
        {cancelled ? <XCircle size={48} className="payment-cancel-icon"/> : checking ? <Loader2 size={48} className="spin payment-wait-icon"/> : <CheckCircle2 size={48} className="payment-success-icon"/>}
        <h1>{cancelled ? 'Đã hủy thanh toán' : checking ? 'Đang xác nhận thanh toán' : confirmed ? 'Nâng cấp thành công' : 'Đã nhận kết quả thanh toán'}</h1>
        <p>{cancelled ? 'Bạn chưa bị trừ tiền và gói hiện tại vẫn được giữ nguyên.' : checking ? 'Hệ thống đang chờ cổng thanh toán xác nhận gói của bạn.' : confirmed ? 'Quyền lợi mới đã được cập nhật vào tài khoản.' : 'Nếu gói chưa đổi ngay, hệ thống sẽ cập nhật sau khi webhook được xác nhận.'}</p>
        <div className="payment-result-actions"><Link to="/dashboard" className="btn btn-primary">Về Dashboard</Link><Link to="/pricing" className="btn btn-ghost">Xem gói cước</Link></div>
      </div>
    </main>
  );
}
