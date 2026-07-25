import { useEffect, useState } from 'react';
import { Camera, KeyRound, Loader2, Save, UserRound } from 'lucide-react';
import { useAuthStore, useUIStore } from '../../store';
import { authService } from '../../services/authService';
import './SettingsPage.css';

export default function SettingsPage() {
  const { user, updateUser } = useAuthStore();
  const { addToast } = useUIStore();
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    fullName: user?.name || '',
    phoneNumber: user?.phoneNumber || '',
    dateOfBirth: user?.dateOfBirth || '',
    avatarUrl: user?.avatar || '',
    password: '',
    confirmPassword: '',
  });

  useEffect(() => {
    setForm((current) => ({
      ...current,
      fullName: user?.name || '',
      avatarUrl: user?.avatar || '',
      phoneNumber: user?.phoneNumber || '',
      dateOfBirth: user?.dateOfBirth || '',
    }));
  }, [user?.avatar, user?.dateOfBirth, user?.name, user?.phoneNumber]);

  const change = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.fullName.trim()) return addToast('Tên hiển thị không được để trống', 'error');
    if (form.password && form.password.length < 8) return addToast('Mật khẩu mới phải có ít nhất 8 ký tự', 'error');
    if (form.password !== form.confirmPassword) return addToast('Mật khẩu xác nhận chưa khớp', 'error');

    setSaving(true);
    try {
      const updated = await authService.updateProfile(user.id, {
        fullName: form.fullName.trim(),
        phoneNumber: form.phoneNumber.trim() || null,
        dateOfBirth: form.dateOfBirth ? form.dateOfBirth.split('-').reverse().join('/') : null,
        avatarUrl: form.avatarUrl.trim() || null,
        password: form.password || null,
      });
      updateUser(updated);
      setForm((current) => ({ ...current, password: '', confirmPassword: '' }));
      addToast('Đã cập nhật tài khoản', 'success');
    } catch (error) {
      addToast(error.message || 'Không thể cập nhật tài khoản', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="settings-page page-enter">
      <div className="settings-shell">
        <header className="settings-heading">
          <div><span className="settings-eyebrow">Tài khoản</span><h1>Thông tin cá nhân</h1><p>Quản lý thông tin hiển thị và bảo mật đăng nhập.</p></div>
          <span className="settings-plan">{(user?.plan || 'free').toUpperCase()}</span>
        </header>
        <form className="settings-form" onSubmit={handleSubmit}>
          <section className="settings-section">
            <div className="settings-section-title"><UserRound size={18}/><span>Hồ sơ</span></div>
            <div className="settings-profile-row">
              <img src={form.avatarUrl || user?.avatar} alt="" className="settings-avatar"/>
              <label className="settings-field grow"><span><Camera size={14}/> URL ảnh đại diện</span><input value={form.avatarUrl} onChange={change('avatarUrl')} placeholder="https://..."/></label>
            </div>
            <div className="settings-grid">
              <label className="settings-field"><span>Tên hiển thị</span><input value={form.fullName} onChange={change('fullName')} maxLength={100}/></label>
              <label className="settings-field"><span>Email</span><input value={user?.email || ''} disabled/></label>
              <label className="settings-field"><span>Số điện thoại</span><input value={form.phoneNumber} onChange={change('phoneNumber')} maxLength={20}/></label>
              <label className="settings-field"><span>Ngày sinh</span><input type="date" value={form.dateOfBirth} onChange={change('dateOfBirth')}/></label>
            </div>
          </section>
          <section className="settings-section">
            <div className="settings-section-title"><KeyRound size={18}/><span>Đổi mật khẩu</span></div>
            <div className="settings-grid">
              <label className="settings-field"><span>Mật khẩu mới</span><input type="password" value={form.password} onChange={change('password')} autoComplete="new-password"/></label>
              <label className="settings-field"><span>Xác nhận mật khẩu</span><input type="password" value={form.confirmPassword} onChange={change('confirmPassword')} autoComplete="new-password"/></label>
            </div>
          </section>
          <div className="settings-actions"><button className="btn btn-primary" type="submit" disabled={saving}>{saving ? <Loader2 size={16} className="spin"/> : <Save size={16}/>} Lưu thay đổi</button></div>
        </form>
      </div>
    </main>
  );
}
