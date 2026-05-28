// pages/balance/balance.js
const api = require('../../utils/api');

Page({
  data: { balance: 0, recharges: [] },

  onShow() { this.loadBalance(); },

  async loadBalance() {
    try {
      const data = await api.getBalance();
      this.setData({ balance: data.balance, recharges: data.recent_recharges || [] });
    } catch (e) {}
  },
});
