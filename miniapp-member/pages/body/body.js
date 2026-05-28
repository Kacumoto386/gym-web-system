// pages/body/body.js
const api = require('../../utils/api');

Page({
  data: { records: [], latest: null },

  onShow() { this.loadData(); },

  async loadData() {
    try {
      const [records, latest] = await Promise.all([
        api.getBodyMeasurements(),
        api.getLatestBodyMeasurement(),
      ]);
      this.setData({ records, latest });
    } catch (e) {}
  },
});
