// pages/home/home.js
const api = require('../../utils/api');

Page({
  data: {
    staffName: '',
    todayCheckins: 0,
    quickSearch: '',
    version: 'S1.0.1',
  },

  onShow() {
    const staffInfo = wx.getStorageSync('staffInfo');
    this.setData({ staffName: staffInfo?.staff_name || '' });
    this.loadTodayCheckins();
  },

  async loadTodayCheckins() {
    try {
      const records = await api.getRecentCheckins();
      this.setData({ todayCheckins: records.length });
    } catch (e) {}
  },

  onSearchInput(e) {
    this.setData({ quickSearch: e.detail.value });
  },

  onQuickSearch() {
    if (this.data.quickSearch) {
      wx.navigateTo({
        url: `/pages/member/member?keyword=${encodeURIComponent(this.data.quickSearch)}`,
      });
    }
  },

  onScanCheckin() {
    wx.navigateTo({ url: '/pages/checkin/checkin' });
  },

  onNavigate(e) {
    const page = e.currentTarget.dataset.page;
    wx.navigateTo({ url: page });
  },
});
