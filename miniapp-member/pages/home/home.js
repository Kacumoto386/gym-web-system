// pages/home/home.js
const api = require('../../utils/api');

Page({
  data: {
    member: null,
    cardCount: 0,
    totalRemaining: 0,
    monthlyCheckins: 0,
    alerts: [],
    version: 'M1.0.1',
  },

  onShow() {
    this.loadProfile();
  },

  async loadProfile() {
    try {
      const [profile, checkinStats, alerts] = await Promise.all([
        api.getProfile(),
        api.getCheckinStats(),
        api.getAlerts(),
      ]);
      this.setData({
        member: profile,
        cardCount: profile?.card_count || 0,
        totalRemaining: profile?.total_remaining || 0,
        monthlyCheckins: checkinStats?.monthly_count || 0,
        alerts: alerts || [],
      });
    } catch (e) {}
  },

  onNavigate(e) {
    const page = e.currentTarget.dataset.page;
    wx.navigateTo({ url: page });
  },
});
