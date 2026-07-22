import apiClient from './apiClient';

const normalizeApiResponse = (response) => {
  if (!response) {
    throw new Error('Không nhận được phản hồi từ máy chủ');
  }

  if (response.code && response.code !== 200 && response.code !== 1000) {
    throw new Error(response.message || 'Yêu cầu thất bại');
  }

  if (typeof response.data !== 'undefined') {
    return response.data;
  }

  return response;
};

export const subscriptionService = {
  // Lấy thông tin subscription hiện tại của user đang đăng nhập
  async getMySubscription() {
    const response = await apiClient.get('/subscription/users');
    return normalizeApiResponse(response.data);
  },

  // Lấy danh sách quota sử dụng hiện tại
  async getMyQuotas() {
    const response = await apiClient.get('/subscription/users/quotas');
    return normalizeApiResponse(response.data);
  },

  // Lấy lịch sử giao dịch nâng cấp gói
  async getMyHistory() {
    const response = await apiClient.get('/subscription/users/history');
    return normalizeApiResponse(response.data);
  },

  // Đăng ký nâng cấp gói
  async upgrade(packageCode, paymentProvider = 'PAYOS', billingCycle = 0) {
    const response = await apiClient.post('/subscription/users/upgrade', {
      packageCode,
      billingCycle,
      paymentProvider
    });
    return normalizeApiResponse(response.data);
  },

  // Hủy gói hiện tại
  async cancel() {
    const response = await apiClient.post('/subscription/users/cancel');
    return normalizeApiResponse(response.data);
  },

  // Kích hoạt lại gói đã hủy
  async reactivate() {
    const response = await apiClient.post('/subscription/users/reactivate');
    return normalizeApiResponse(response.data);
  },

  // Lấy danh sách các gói cước đang hoạt động
  async getPackages() {
    const response = await apiClient.get('/subscription/packages');
    return normalizeApiResponse(response.data);
  },

  // Lấy chi tiết gói cước theo code
  async getPackageByCode(code) {
    const response = await apiClient.get(`/subscription/packages/${code}`);
    return normalizeApiResponse(response.data);
  }
};
