// pages/performance/performance.js
const api = require('../../utils/api');

Page({
  data: {
    summary: null,
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1,
  },

  onShow() {
    this.loadSummary();
  },

  async loadSummary() {
    try {
      const data = await api.getPerformanceSummary(this.data.year, this.data.month);
      this.setData({ summary: data });
    } catch (e) {}
  },
});
