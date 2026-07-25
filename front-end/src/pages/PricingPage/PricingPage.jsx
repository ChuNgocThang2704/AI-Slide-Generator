import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, useUIStore } from '../../store';
import { Check, Sparkles, Zap, Crown, Loader2 } from 'lucide-react';
import { subscriptionService } from '../../services/subscriptionService';
import './PricingPage.css';

const PLANS = [
  {
    id: 'free',
    name: 'Free',
    price: '0',
    period: 'mãi mãi',
    desc: 'Lý tưởng để bắt đầu trải nghiệm',
    icon: <Sparkles size={22} />,
    color: '#6c63ff',
    features: [
      'Tối đa 10 slides / presentation',
      'Tối đa 5 hình ảnh / presentation',
      'Giới hạn 10.000 ký tự nội dung',
      '2 lượt chỉnh sửa bằng AI mỗi ngày',
      'Xuất PDF chất lượng cao',
      '6 template thiết kế cơ bản',
    ],
    notIncluded: ['Xuất tệp PPTX (PowerPoint)', 'AI ảnh chất lượng HD', 'Ưu tiên xử lý nhanh'],
  },
  {
    id: 'pro',
    name: 'Pro',
    price: '20',
    period: 'tháng',
    desc: 'Dành cho cá nhân và chuyên nghiệp',
    icon: <Zap size={22} />,
    color: '#f72585',
    popular: true,
    features: [
      'Tối đa 30 slides / presentation',
      'Tối đa 15 hình ảnh / presentation',
      'Giới hạn 50.000 ký tự nội dung',
      '10 lượt chỉnh sửa bằng AI mỗi ngày',
      'Xuất tệp PPTX (PowerPoint) & PDF',
      'Mở khóa toàn bộ template + template mới',
      'Ưu tiên xử lý nhanh từ hệ thống',
    ],
    notIncluded: ['API Access', 'Hỗ trợ VIP 24/7'],
  },
  {
    id: 'ultra',
    name: 'Ultra',
    price: '49',
    period: 'tháng',
    desc: 'Dành cho đội ngũ và doanh nghiệp',
    icon: <Crown size={22} />,
    color: '#fbbf24',
    features: [
      'Tối đa 50 slides / presentation',
      'Tối đa 35 hình ảnh / presentation',
      'Giới hạn 100.000 ký tự nội dung',
      '30 lượt chỉnh sửa bằng AI mỗi ngày',
      'Xuất tệp PPTX, PDF & hình ảnh PNG',
      'Mở khóa toàn bộ template nâng cao',
      'Ưu tiên xử lý siêu nhanh (High Priority)',
      'Hỗ trợ VIP 24/7',
      'Quyền truy cập API Access',
    ],
    notIncluded: [],
  },
];

export default function PricingPage() {
  const { isAuthenticated, user, updateUser } = useAuthStore();
  const { addToast } = useUIStore();
  const navigate = useNavigate();

  const [loadingPlan, setLoadingPlan] = useState(null);
  const [subDetail, setSubDetail] = useState(null);
  const [loadingSub, setLoadingSub] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [quotas, setQuotas] = useState([]);
  const [history, setHistory] = useState([]);

  // Payment modal state
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [paymentProvider, setPaymentProvider] = useState('PAYOS'); // 'PAYOS' or 'STRIPE'
  const [billingCycle, setBillingCycle] = useState(0); // 0 = monthly, 1 = yearly

  const loadQuotas = async () => {
    if (!isAuthenticated) return;
    try {
      const data = await subscriptionService.getMyQuotas();
      setQuotas(data || []);
    } catch (err) {
      console.error('Lỗi lấy quotas:', err);
    }
  };

  const loadHistory = async () => {
    if (!isAuthenticated) return;
    try {
      const data = await subscriptionService.getMyHistory();
      setHistory(data || []);
    } catch (err) {
      console.error('Lỗi lấy lịch sử:', err);
    }
  };

  const loadSubscription = async () => {
    if (!isAuthenticated) return;
    setLoadingSub(true);
    try {
      const data = await subscriptionService.getMySubscription();
      setSubDetail(data);
      if (data && data.packageCode) {
        updateUser({ plan: data.packageCode.toLowerCase() });
      }
      await loadQuotas();
      await loadHistory();
    } catch (err) {
      console.error('Lỗi lấy subscription:', err);
    } finally {
      setLoadingSub(false);
    }
  };

  useEffect(() => {
    loadSubscription();
  }, [isAuthenticated]);

  const handleChoose = async (planId) => {
    if (!isAuthenticated) { navigate('/register'); return; }

    if (planId === 'free') {
      setLoadingPlan('free');
      try {
        await subscriptionService.upgrade('FREE');
        addToast('Đã quay lại gói Free thành công', 'success');
        updateUser({ plan: 'free' });
        await loadSubscription();
      } catch (err) {
        console.error(err);
        addToast(err.message || 'Thao tác thất bại', 'error');
      } finally {
        setLoadingPlan(null);
      }
      return;
    }

    // Mở modal thanh toán cho Pro hoặc Ultra
    setSelectedPlanId(planId);
    setShowPaymentModal(true);
  };

  const handlePaymentSubmit = async () => {
    if (!selectedPlanId) return;
    setLoadingPlan(selectedPlanId);
    setShowPaymentModal(false);
    
    try {
      const pkgCode = selectedPlanId.toUpperCase(); // 'PRO' or 'ULTRA'
      addToast('Đang khởi tạo liên kết thanh toán...', 'info');
      
      const response = await subscriptionService.upgrade(pkgCode, paymentProvider, billingCycle);
      
      if (response && response.paymentRedirectUrl) {
        addToast('Đang chuyển hướng sang trang thanh toán...', 'success');
        window.location.href = response.paymentRedirectUrl;
      } else {
        addToast('Khởi tạo liên kết thanh toán thành công, vui lòng chờ xử lý.', 'success');
        await loadSubscription();
      }
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Khởi tạo thanh toán thất bại', 'error');
    } finally {
      setLoadingPlan(null);
    }
  };

  const handleCancel = async () => {
    if (!window.confirm('Bạn có chắc muốn hủy tự động gia hạn gói cước này? Gói vẫn sẽ hoạt động đến ngày hết hạn.')) return;
    setActionLoading(true);
    try {
      await subscriptionService.cancel();
      addToast('Đã hủy tự động gia hạn thành công', 'success');
      await loadSubscription();
    } catch (err) {
      addToast(err.message || 'Không thể hủy gia hạn', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReactivate = async () => {
    setActionLoading(true);
    try {
      await subscriptionService.reactivate();
      addToast('Kích hoạt lại gói cước thành công!', 'success');
      await loadSubscription();
    } catch (err) {
      addToast(err.message || 'Không thể kích hoạt lại gói cước', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="pricing-page page-enter">
      <div className="pricing-glow" />
      <div className="container">
        <div className="pricing-header">
          <div className="section-badge">Bảng giá</div>
          <h1>Chọn gói phù hợp<br /><span className="gradient-text">với bạn</span></h1>
          <p style={{ color: 'rgba(255,255,255,0.5)', maxWidth: 480, margin: '0 auto' }}>
            Bắt đầu miễn phí, nâng cấp bất cứ lúc nào. Không có phí ẩn.
          </p>
        </div>

        {/* Current subscription & quotas management section */}
        {isAuthenticated && (loadingSub ? (
          <div style={{ display: 'flex', justifyContent: 'center', margin: '20px 0 40px' }}>
            <Loader2 className="spin" size={24} style={{ color: '#6c63ff' }} />
          </div>
        ) : subDetail ? (
          <div className="sub-management-grid">
            <div className="current-sub-card">
              <div className="csc-header">
                <h3>Gói cước hiện tại</h3>
                <span className={`sub-status-badge status-${subDetail.status}`}>
                  {subDetail.status === 1 ? '🟢 Đang hoạt động' : subDetail.status === 3 ? '🟡 Đã hủy gia hạn' : '⚪ Hết hạn'}
                </span>
              </div>
              <div className="csc-body">
                <div className="csc-info-item">
                  <span className="csc-label">Gói:</span>
                  <strong className="csc-val" style={{ color: PLANS.find(p=>p.id === subDetail.packageCode.toLowerCase())?.color || '#a855f7' }}>
                    {subDetail.packageName || subDetail.packageCode}
                  </strong>
                </div>
                {subDetail.startDate && (
                  <div className="csc-info-item">
                    <span className="csc-label">Ngày bắt đầu:</span>
                    <span className="csc-val">{new Date(subDetail.startDate).toLocaleDateString('vi-VN')}</span>
                  </div>
                )}
                {subDetail.expireDate && (
                  <div className="csc-info-item">
                    <span className="csc-label">Ngày hết hạn:</span>
                    <span className="csc-val">{new Date(subDetail.expireDate).toLocaleDateString('vi-VN')}</span>
                  </div>
                )}
                
                {subDetail.packageCode !== 'FREE' && (
                  <div className="csc-actions">
                    {subDetail.status === 1 ? (
                      <button className="btn btn-ghost btn-sm danger-hover" onClick={handleCancel} disabled={actionLoading} style={{ marginTop: 12 }}>
                        {actionLoading ? <Loader2 size={13} className="spin" /> : null} Hủy gia hạn
                      </button>
                    ) : subDetail.status === 3 ? (
                      <button className="btn btn-primary btn-sm" onClick={handleReactivate} disabled={actionLoading} style={{ marginTop: 12 }}>
                        {actionLoading ? <Loader2 size={13} className="spin" /> : null} Kích hoạt lại
                      </button>
                    ) : null}
                  </div>
                )}
              </div>
            </div>

            {quotas.length > 0 && (
              <div className="quotas-card">
                <h3>Hạn mức sử dụng của bạn</h3>
                <div className="quotas-list">
                  {quotas.map((q) => {
                    const percentage = Math.min(100, (q.currentUsage / q.limitValue) * 100);
                    return (
                      <div key={q.featureKey} className="quota-progress-item">
                        <div className="qpi-label-wrap">
                          <span className="qpi-title">{q.displayName || q.featureKey}</span>
                          <span className="qpi-value">{q.currentUsage} / {q.limitValue}</span>
                        </div>
                        <div className="qpi-bar-bg">
                          <div className="qpi-bar-fill" style={{ width: `${percentage}%`, background: percentage > 85 ? '#ef4444' : '#10b981' }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {history.length > 0 && (
              <div className="current-sub-card" style={{ gridColumn: 'span 2', marginTop: 12 }}>
                <h3 style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: 12, marginBottom: 12 }}>Lịch sử nâng cấp</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 200, overflowY: 'auto', paddingRight: 6 }}>
                  {history.map((h) => {
                    const actionLabels = {
                      0: 'Khởi tạo gói',
                      1: 'Nâng cấp',
                      2: 'Hạ cấp',
                      3: 'Hủy gia hạn',
                      4: 'Gia hạn/Kích hoạt lại'
                    };
                    return (
                      <div key={h.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', paddingBottom: 8, borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                        <div>
                          <strong style={{ color: 'white' }}>{actionLabels[h.action] || 'Giao dịch'}</strong>
                          {h.newPackageCode && <span style={{ marginLeft: 8, color: '#f72585', fontSize: '0.78rem', background: 'rgba(247,37,133,0.1)', padding: '2px 8px', borderRadius: 4 }}>{h.newPackageCode}</span>}
                          {h.note && <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.75rem', marginTop: 2 }}>{h.note}</div>}
                        </div>
                        <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.8rem' }}>{new Date(h.createdAt).toLocaleString('vi-VN')}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : null)}

        <div className="plans-grid">
          {PLANS.map((plan) => {
            const isCurrent = user?.plan === plan.id;
            return (
              <div key={plan.id} className={`plan-card ${plan.popular ? 'popular' : ''}`}>
                {plan.popular && (
                  <div className="plan-popular-badge">🔥 Phổ biến nhất</div>
                )}
                <div className="plan-icon" style={{ background: plan.color + '18', color: plan.color }}>
                  {plan.icon}
                </div>
                <div className="plan-name" style={{ color: plan.color }}>{plan.name}</div>
                <div className="plan-price">
                  <span className="price-currency">$</span>
                  <span className="price-amount">{plan.price}</span>
                  <span className="price-period">/{plan.period}</span>
                </div>
                <p className="plan-desc">{plan.desc}</p>
                <div className="plan-divider" style={{ background: plan.color + '40' }} />

                <ul className="plan-features">
                  {plan.features.map((f) => (
                    <li key={f} className="feature-item included">
                      <Check size={14} style={{ color: plan.color, flexShrink: 0 }} />
                      <span>{f}</span>
                    </li>
                  ))}
                  {plan.notIncluded?.map((f) => (
                    <li key={f} className="feature-item not-included">
                      <span className="feature-cross">×</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>

                <button
                  className={`plan-btn ${plan.popular ? 'plan-btn-primary' : 'plan-btn-secondary'}`}
                  style={plan.popular && !isCurrent ? { background: `linear-gradient(135deg, ${plan.color}, #a855f7)` } : {}}
                  onClick={() => handleChoose(plan.id)}
                  disabled={loadingPlan !== null || isCurrent}
                >
                  {loadingPlan === plan.id ? (
                    <Loader2 size={15} className="spin" style={{ margin: '0 auto' }} />
                  ) : isCurrent ? (
                    '✓ Gói hiện tại'
                  ) : plan.id === 'free' ? (
                    'Bắt đầu miễn phí'
                  ) : (
                    `Chọn gói ${plan.name}`
                  )}
                </button>
              </div>
            );
          })}
        </div>

        {/* Payment Modal */}
        {showPaymentModal && selectedPlanId && (
          <div className="payment-modal-overlay">
            <div className="payment-modal-card">
              <div className="pmc-header">
                <h3>Nâng cấp gói {selectedPlanId.toUpperCase()}</h3>
                <button className="pmc-close-btn" onClick={() => setShowPaymentModal(false)}>×</button>
              </div>
              
              <div className="pmc-body">
                {/* Billing Cycle Selection */}
                <div className="pmc-section">
                  <span className="pmc-section-title">Chu kỳ thanh toán</span>
                  <div className="pmc-options">
                    <button 
                      className={`pmc-option-btn ${billingCycle === 0 ? 'active' : ''}`}
                      onClick={() => setBillingCycle(0)}
                    >
                      Hằng tháng
                    </button>
                    <button 
                      className={`pmc-option-btn ${billingCycle === 1 ? 'active' : ''}`}
                      onClick={() => setBillingCycle(1)}
                    >
                      Hằng năm (Tiết kiệm)
                    </button>
                  </div>
                </div>

                {/* Payment Provider Selection */}
                <div className="pmc-section">
                  <span className="pmc-section-title">Phương thức thanh toán</span>
                  <div className="pmc-provider-list">
                    <div 
                      className={`pmc-provider-item ${paymentProvider === 'PAYOS' ? 'active' : ''}`}
                      onClick={() => setPaymentProvider('PAYOS')}
                    >
                      <div className="pmc-provider-dot" />
                      <div className="pmc-provider-details">
                        <strong>VietQR / PayOS (VNĐ)</strong>
                        <span>Chuyển khoản nhanh qua app Ngân hàng Việt Nam</span>
                      </div>
                    </div>
                    
                    <div 
                      className={`pmc-provider-item ${paymentProvider === 'STRIPE' ? 'active' : ''}`}
                      onClick={() => setPaymentProvider('STRIPE')}
                    >
                      <div className="pmc-provider-dot" />
                      <div className="pmc-provider-details">
                        <strong>Thẻ Quốc tế / Stripe (USD)</strong>
                        <span>Thanh toán Visa, Mastercard, JCB quốc tế</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Price Details */}
                <div className="pmc-price-box">
                  <span className="pmc-price-label">Số tiền cần thanh toán:</span>
                  <span className="pmc-price-value">
                    {selectedPlanId === 'pro' ? (
                      paymentProvider === 'PAYOS' ? (
                        billingCycle === 0 ? '199.000 VNĐ / tháng' : '1.990.000 VNĐ / năm'
                      ) : (
                        billingCycle === 0 ? '$10 USD / tháng' : '$100 USD / năm'
                      )
                    ) : (
                      paymentProvider === 'PAYOS' ? (
                        billingCycle === 0 ? '499.000 VNĐ / tháng' : '4.990.000 VNĐ / năm'
                      ) : (
                        billingCycle === 0 ? '$20 USD / tháng' : '$200 USD / năm'
                      )
                    )}
                  </span>
                </div>
              </div>

              <div className="pmc-footer">
                <button className="btn btn-secondary" onClick={() => setShowPaymentModal(false)}>
                  Hủy bỏ
                </button>
                <button className="btn btn-primary" onClick={handlePaymentSubmit} style={{
                  background: selectedPlanId === 'pro' ? '#f72585' : '#fbbf24',
                  color: selectedPlanId === 'pro' ? 'white' : 'black',
                  fontWeight: 'bold',
                  border: 'none',
                  borderRadius: '10px',
                  padding: '10px 20px',
                  cursor: 'pointer'
                }}>
                  Thanh toán ngay
                </button>
              </div>
            </div>
          </div>
        )}

        {/* FAQ */}
        <div className="pricing-faq">
          <h2 style={{ textAlign: 'center', marginBottom: 40 }}>Câu hỏi thường gặp</h2>
          <div className="faq-grid">
            {[
              { q: 'Tôi có thể hủy bất cứ lúc nào không?', a: 'Có, bạn có thể hủy gói bất cứ lúc nào. Gói sẽ vẫn hoạt động đến hết chu kỳ thanh toán.' },
              { q: 'Xuất PDF có giữ nguyên định dạng không?', a: 'Có, slide được xuất PDF với đúng màu sắc, font chữ và bố cục như trên web.' },
              { q: 'AI tạo slide có chính xác không?', a: 'AI được fine-tune để tạo nội dung chuyên nghiệp. Bạn vẫn có thể chỉnh sửa trực tiếp sau khi tạo.' },
              { q: 'Có giới hạn nào trong gói Free không?', a: 'Gói Free cho phép tạo 5 slides/tháng và lưu tối đa 10 presentations. Đủ để bạn trải nghiệm.' },
            ].map((faq, i) => (
              <div key={i} className="faq-card">
                <h4 className="faq-q">{faq.q}</h4>
                <p className="faq-a">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
