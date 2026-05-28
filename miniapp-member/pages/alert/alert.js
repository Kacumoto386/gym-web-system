// pages/alert/alert.js
const api = require('../../utils/api');

Page({
  data: { alerts: [] },

  onShow() { this.loadAlerts(); },

  async loadAlerts() {
    try { const data = await api.getAlerts(); this.setData({ alerts: data }); } catch (e) {}
  },
});
