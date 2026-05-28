// pages/checkin/checkin.js
const api = require('../../utils/api');

Page({
  data: { records: [], stats: null, page: 1 },

  onShow() {
    this.loadData();
  },

  async loadData() {
    try {
      const [records, stats] = await Promise.all([
        api.getCheckins(this.data.page),
        api.getCheckinStats(),
      ]);
      this.setData({ records: records.items, stats });
    } catch (e) {}
  },
});
