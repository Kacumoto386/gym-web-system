// pages/class-record/class-record.js
const api = require('../../utils/api');

Page({
  data: { records: [], stats: null, page: 1, hasMore: true },

  onShow() { this.loadData(); },

  async loadData() {
    try {
      const [records, stats] = await Promise.all([
        api.getClassRecords(this.data.page),
        api.getClassRecordStats(),
      ]);
      this.setData({ records: records.items, stats, hasMore: records.has_more });
    } catch (e) {}
  },

  onLoadMore() {
    if (this.data.hasMore) {
      this.setData({ page: this.data.page + 1 });
      this.loadData();
    }
  },
});
