//app.js
App({
  onLaunch() {
    const token = wx.getStorageSync('token');
    if (!token) {
      wx.redirectTo({ url: '/pages/login/login' });
    }
  },

  globalData: {
    token: '',
    memberInfo: null,
    apiBaseUrl: 'http://localhost:8080/api/miniapp/member',
    version: 'M1.0.1',
  }
});
