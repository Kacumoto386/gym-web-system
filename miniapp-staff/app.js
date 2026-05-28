//app.js
App({
  onLaunch() {
    // 检查登录状态
    const token = wx.getStorageSync('token');
    if (!token) {
      wx.redirectTo({ url: '/pages/login/login' });
    }
  },

  globalData: {
    token: '',
    staffInfo: null,
    apiBaseUrl: 'http://localhost:8080/api/miniapp/staff',
    version: 'S1.0.1',
  }
});
