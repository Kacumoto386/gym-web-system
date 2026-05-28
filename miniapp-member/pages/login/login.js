// pages/login/login.js
const api = require('../../utils/api');

Page({
  data: {
    phone: '',
    password: '',
    code: '',
    tabIndex: 0,
    loading: false,
    codeSending: false,
    codeCountdown: 0,
  },

  // ── Tab 切换 ──
  switchTab(e) {
    const index = parseInt(e.currentTarget.dataset.index);
    this.setData({ tabIndex: index });
  },
  switchToCodeTab() {
    this.setData({ tabIndex: 1 });
  },
  switchToPwdTab() {
    this.setData({ tabIndex: 0 });
  },

  // ── 输入 ──
  onInputPhone(e) {
    this.setData({ phone: e.detail.value });
  },
  onInputPassword(e) {
    this.setData({ password: e.detail.value });
  },
  onInputCode(e) {
    this.setData({ code: e.detail.value });
  },

  // ── 发送验证码 ──
  async onSendCode() {
    if (!this.data.phone) {
      wx.showToast({ title: '请输入手机号', icon: 'none' });
      return;
    }
    this.setData({ codeSending: true });
    try {
      await api.sendCode(this.data.phone);
      wx.showToast({ title: '验证码已发送', icon: 'success' });
      // 60s 倒计时
      let countdown = 60;
      this.setData({ codeCountdown: countdown, codeSending: false });
      this._codeTimer = setInterval(() => {
        countdown -= 1;
        if (countdown <= 0) {
          clearInterval(this._codeTimer);
          this.setData({ codeCountdown: 0 });
        } else {
          this.setData({ codeCountdown: countdown });
        }
      }, 1000);
    } catch (e) {
      this.setData({ codeSending: false });
    }
  },

  // ── 密码登录 ──
  async onLoginByPassword() {
    if (!this.data.phone) {
      wx.showToast({ title: '请输入手机号', icon: 'none' });
      return;
    }
    if (!this.data.password) {
      wx.showToast({ title: '请输入密码', icon: 'none' });
      return;
    }
    this.setData({ loading: true });
    try {
      const result = await api.loginByPassword({
        phone: this.data.phone,
        password: this.data.password,
      });
      wx.setStorageSync('token', result.token);
      wx.setStorageSync('memberInfo', result);
      wx.switchTab({ url: '/pages/home/home' });
    } catch (e) {}
    this.setData({ loading: false });
  },

  // ── 验证码登录 ──
  async onLoginByCode() {
    if (!this.data.phone) {
      wx.showToast({ title: '请输入手机号', icon: 'none' });
      return;
    }
    if (!this.data.code) {
      wx.showToast({ title: '请输入验证码', icon: 'none' });
      return;
    }
    this.setData({ loading: true });
    try {
      const result = await api.loginByCode({
        phone: this.data.phone,
        code: this.data.code,
      });
      wx.setStorageSync('token', result.token);
      wx.setStorageSync('memberInfo', result);
      wx.switchTab({ url: '/pages/home/home' });
    } catch (e) {}
    this.setData({ loading: false });
  },

  // ── 微信一键登录（保留） ──
  async onLogin() {
    if (!this.data.phone) {
      wx.showToast({ title: '请输入手机号', icon: 'none' });
      return;
    }
    this.setData({ loading: true });
    try {
      const result = await api.login({
        code: 'mock_code',
        phone: this.data.phone,
      });
      wx.setStorageSync('token', result.token);
      wx.setStorageSync('memberInfo', result);
      wx.switchTab({ url: '/pages/home/home' });
    } catch (e) {}
    this.setData({ loading: false });
  },

  onGetPhoneNumber(e) {
    if (e.detail.errMsg === 'getPhoneNumber:ok') {
      wx.showToast({ title: '已获取手机号', icon: 'success' });
    }
  },

  onUnload() {
    if (this._codeTimer) {
      clearInterval(this._codeTimer);
    }
  },
});
