// pages/class-record/class-record.js
const api = require('../../utils/api');

Page({
  data: {
    records: [],
    page: 1,
    hasMore: true,
  },

  onShow() {
    this.loadRecords();
  },

  async loadRecords() {
    try {
      const data = await api.getClassRecords({ page: this.data.page, pageSize: 20 });
      this.setData({
        records: [...this.data.records, ...data.items],
        hasMore: data.has_more,
      });
    } catch (e) {}
  },

  onLoadMore() {
    if (this.data.hasMore) {
      this.setData({ page: this.data.page + 1 });
      this.loadRecords();
    }
  },
});
