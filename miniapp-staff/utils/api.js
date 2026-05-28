const API_BASE = getApp().globalData.apiBaseUrl;

function request(method, path, data = {}) {
  const token = wx.getStorageSync('token');
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE}${path}`,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
      success(res) {
        if (res.data.code === 0) {
          resolve(res.data.data);
        } else {
          wx.showToast({ title: res.data.message || '请求失败', icon: 'none' });
          reject(res.data);
        }
      },
      fail(err) {
        wx.showToast({ title: '网络错误', icon: 'none' });
        reject(err);
      },
    });
  });
}

module.exports = {
  // 认证
  login: (data) => request('POST', '/auth/login', data),
  logout: () => request('POST', '/auth/logout'),

  // 会员
  createMember: (data) => request('POST', '/members', data),
  updateMember: (id, data) => request('PUT', `/members/${id}`, data),
  searchMember: (keyword) => request('GET', `/members/search?keyword=${encodeURIComponent(keyword)}`),
  getMember: (id) => request('GET', `/members/${id}`),
  getMemberCheckins: (id) => request('GET', `/members/${id}/checkins`),

  // 购卡
  getCardProducts: () => request('GET', '/cards/products'),
  sellCard: (data) => request('POST', '/cards/sell', data),

  // 购课
  getPackages: () => request('GET', '/sales/packages'),
  createSale: (data) => request('POST', '/sales', data),

  // 预约
  getCoaches: () => request('GET', '/bookings/coaches'),
  getCoachSlots: (coachId, date) => request('GET', `/bookings/slots?coach_id=${coachId}&date=${date}`),
  createBooking: (data) => request('POST', '/bookings', data),
  cancelBooking: (id) => request('PUT', `/bookings/${id}/cancel`),

  // 核销
  scanCheckin: (data) => request('POST', '/checkin/scan', data),
  getRecentCheckins: () => request('GET', '/checkin/recent'),

  // 上课记录
  getClassRecords: (params) => request('GET', `/class-records?page=${params.page || 1}&page_size=${params.pageSize || 20}`),
  createClassRecord: (data) => request('POST', '/class-records', data),

  // 业绩
  getPerformanceSummary: (year, month) => request('GET', `/performance/summary?year=${year}&month=${month}`),
  getPerformanceSales: (year, month) => request('GET', `/performance/sales?year=${year}&month=${month}`),
  getPerformanceCommission: (year, month) => request('GET', `/performance/commission?year=${year}&month=${month}`),
};
