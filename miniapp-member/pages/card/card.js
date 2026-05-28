// pages/card/card.js
const api = require('../../utils/api');

Page({
  data: { cards: [] },

  onShow() { this.loadCards(); },

  async loadCards() {
    try {
      const cards = await api.getCards();
      this.setData({ cards });
    } catch (e) {}
  },

  onViewDetail(e) {
    wx.navigateTo({ url: `/pages/card/detail?card_id=${e.currentTarget.dataset.id}` });
  },
});
