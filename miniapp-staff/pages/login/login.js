// pages/login/login.js
const api = require('../../utils/api');

Page({
  data: {
    username: '',
    password: '',
    loading: false,
  },

  onInputUsername(e) {
    this.setData({ username: e.detail.value });
  },

  onInputPassword(e) {
    this.setData({ password: e.detail.value });
  },

  async onLogin() {
    const { username, password } = this.data;
    if (!username || !password) {
      wx.showToast({ title: '请输入账号和密码', icon: 'none' });
      return;
    }

    this.setData({ loading: true });
    try {
      const result = await api.login({ username, password });
      wx.setStorageSync('token', result.token);
      wx.setStorageSync('staffInfo', result);
      wx.switchTab({ url: '/pages/home/home' });
    } catch (e) {
      // 错误已在 api 中处理
    } finally {
      this.setData({ loading: false });
    }
  },
});
