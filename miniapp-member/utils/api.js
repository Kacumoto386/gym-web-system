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
  sendCode: (phone) => request('POST', '/auth/send-code', { phone }),
  loginByPassword: (data) => request('POST', '/auth/login-by-password', data),
  loginByCode: (data) => request('POST', '/auth/login-by-code', data),
  setPassword: (data) => request('POST', '/auth/set-password', data),

  // 首页
  getProfile: () => request('GET', '/profile'),
  getDashboard: () => request('GET', '/profile/dashboard'),

  // 会籍卡
  getCards: () => request('GET', '/cards'),
  getCardDetail: (id) => request('GET', `/cards/${id}`),
  getCardHistory: (id) => request('GET', `/cards/${id}/history`),

  // 储值
  getBalance: () => request('GET', '/balance'),
  getRechargeHistory: () => request('GET', '/balance/history'),

  // 签到
  getCheckins: (page) => request('GET', `/checkins?page=${page}&page_size=20`),
  getCheckinStats: () => request('GET', '/checkins/stats'),

  // 预约
  getBookings: (status) => request('GET', `/bookings${status ? `?status=${status}` : ''}`),
  getCoaches: () => request('GET', '/bookings/coaches'),
  createBooking: (data) => request('POST', '/bookings', data),
  cancelBooking: (id) => request('PUT', `/bookings/${id}/cancel`),

  // 上课
  getClassRecords: (page) => request('GET', `/class-records?page=${page}&page_size=20`),
  getClassRecordStats: () => request('GET', '/class-records/stats'),

  // 体测
  getBodyMeasurements: () => request('GET', '/body-measurements'),
  getLatestBodyMeasurement: () => request('GET', '/body-measurements/latest'),

  // 到期提醒
  getAlerts: () => request('GET', '/alerts'),

  // 购买
  getCardProducts: () => request('GET', '/purchase/card-products'),
  getPackages: () => request('GET', '/purchase/packages'),
  createOrder: (data) => request('POST', '/purchase/create-order', data),
  getOrders: (status) => request('GET', `/purchase/orders${status ? `?status=${status}` : ''}`),
  prepay: (orderId) => request('POST', `/purchase/prepay?order_id=${orderId}`),
  pay: (orderId) => request('POST', `/purchase/pay?order_id=${orderId}`),
};
