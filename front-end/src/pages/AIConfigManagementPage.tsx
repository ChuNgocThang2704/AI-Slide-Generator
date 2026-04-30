import React, { useState, useEffect } from 'react';
import { aiConfigApi, type AiConfig } from '../api/aiConfig';
import { roleApi, type Role } from '../api/role';
import { Plus, Save, Trash2, Loader2, AlertCircle } from 'lucide-react';
import Layout from '../components/Layout';
import './AIConfigManagement.css';
import { toast } from 'react-hot-toast';

const AIConfigManagementPage: React.FC = () => {
  const [configs, setConfigs] = useState<AiConfig[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([fetchConfigs(), fetchRoles()]).finally(() => setLoading(false));
  }, []);

  const fetchRoles = async () => {
    try {
      const res = await roleApi.getAll();
      setRoles(res.data.data);
    } catch (err) {
      toast.error('Không thể tải danh sách Role');
    }
  };

  const fetchConfigs = async () => {
    try {
      const res = await aiConfigApi.getAll();
      setConfigs(res.data.data);
    } catch (err) {
      toast.error('Không thể tải danh sách cấu hình');
    }
  };

  const handleUpdate = (index: number, field: keyof AiConfig, value: any) => {
    const newConfigs = [...configs];
    newConfigs[index] = { ...newConfigs[index], [field]: value };
    setConfigs(newConfigs);
  };

  const handleAdd = () => {
    const newConfig: AiConfig = {
      roleCode: roles.length > 0 ? roles[0].name : '',
      configName: '',
      language: 'Vietnamese',
      tone: 'Professional',
      maxProjectsPerDay: 5,
      minPagesPerProject: 5,
      maxPagesPerProject: 20
    };
    setConfigs([...configs, newConfig]);
  };

  const handleDelete = (index: number) => {
    const newConfigs = configs.filter((_, i) => i !== index);
    setConfigs(newConfigs);
  };

  const handleSyncAll = async () => {
    setSaving(true);
    try {
      const res = await aiConfigApi.sync(configs);
      setConfigs(res.data.data);
      toast.success('Đã lưu toàn bộ cấu hình');
    } catch (err: any) {
      toast.error(err.response?.data?.message || 'Có lỗi xảy ra khi lưu');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="animate-spin text-indigo-500" size={48} />
      </div>
    );
  }

  return (
    <Layout>
      <div className="ai-config-mgmt-container">
        <div className="ai-config-header">
          <div>
            <h1>Cấu hình AI System</h1>
            <p className="text-slate-400 mt-2">Quản lý các gói dịch vụ và giới hạn AI cho từng cấp độ người dùng</p>
          </div>
          <div className="ai-config-actions">
            <button className="btn-add" onClick={handleAdd}>
              <Plus size={20} /> Thêm cấu hình
            </button>
            <button className="btn-save" onClick={handleSyncAll} disabled={saving}>
              {saving ? <Loader2 className="animate-spin" size={20} /> : <Save size={20} />}
              Lưu tất cả
            </button>
          </div>
        </div>

        <div className="table-wrapper">
          <div className="table-scroll">
            <table className="ai-config-table">
              <thead>
                <tr>
                  <th>Role Code</th>
                  <th>Config Name</th>
                  <th>Language</th>
                  <th>Tone</th>
                  <th>Max Proj/Day</th>
                  <th>Min Pages</th>
                  <th>Max Pages</th>
                  <th style={{ width: '80px' }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {configs.map((config, idx) => (
                  <tr key={config.id || `new-${idx}`}>
                    <td>
                      <select 
                        className="ai-config-select"
                        value={config.roleCode} 
                        onChange={e => handleUpdate(idx, 'roleCode', e.target.value)}
                      >
                        <option value="" disabled>Chọn Role</option>
                        {roles.map(role => (
                          <option key={role.name} value={role.name}>
                            {role.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input 
                        type="text" 
                        value={config.configName} 
                        onChange={e => handleUpdate(idx, 'configName', e.target.value)}
                      />
                    </td>
                    <td>
                      <input 
                        type="text" 
                        value={config.language} 
                        onChange={e => handleUpdate(idx, 'language', e.target.value)}
                      />
                    </td>
                    <td>
                      <input 
                        type="text" 
                        value={config.tone} 
                        onChange={e => handleUpdate(idx, 'tone', e.target.value)}
                      />
                    </td>
                    <td>
                      <input 
                        type="number" 
                        value={config.maxProjectsPerDay} 
                        onChange={e => handleUpdate(idx, 'maxProjectsPerDay', parseInt(e.target.value))}
                      />
                    </td>
                    <td>
                      <input 
                        type="number" 
                        value={config.minPagesPerProject} 
                        onChange={e => handleUpdate(idx, 'minPagesPerProject', parseInt(e.target.value))}
                      />
                    </td>
                    <td>
                      <input 
                        type="number" 
                        value={config.maxPagesPerProject} 
                        onChange={e => handleUpdate(idx, 'maxPagesPerProject', parseInt(e.target.value))}
                      />
                    </td>
                    <td>
                      <button className="btn-delete" onClick={() => handleDelete(idx)}>
                        <Trash2 size={18} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        
        {configs.length === 0 && (
          <div className="flex flex-col items-center justify-center p-20 text-slate-500">
            <AlertCircle size={48} className="mb-4 opacity-20" />
            <p>Chưa có cấu hình nào. Hãy nhấn "Thêm cấu hình" để bắt đầu.</p>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default AIConfigManagementPage;
