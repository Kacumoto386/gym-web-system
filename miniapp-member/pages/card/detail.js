// pages/card/detail.js
const api = require('../../utils/api');

Page({
  data: { card: null, history: [] },

  onLoad(query) {
    if (query.card_id) {
      this.loadCard(query.card_id);
      this.loadHistory(query.card_id);
    }
  },

  async loadCard(id) {
    try { const data = await api.getCardDetail(id); this.setData({ card: data }); } catch (e) {}
  },

  async loadHistory(id) {
    try { const data = await api.getCardHistory(id); this.setData({ history: data }); } catch (e) {}
  },
});
