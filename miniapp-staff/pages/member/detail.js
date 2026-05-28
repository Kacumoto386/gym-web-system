// pages/member/detail.js
const api = require('../../utils/api');

Page({
  data: {
    memberId: '',
    member: null,
    cards: [],
  },

  onLoad(query) {
    if (query.member_id) {
      this.setData({ memberId: query.member_id });
      this.loadMember();
    }
  },

  async loadMember() {
    try {
      const data = await api.getMember(this.data.memberId);
      this.setData({ member: data, cards: data.cards || [] });
      wx.setNavigationBarTitle({ title: data.name });
    } catch (e) {}
  },

  onSellCard() {
    wx.navigateTo({ url: `/pages/card-sale/card-sale?member_id=${this.data.memberId}` });
  },

  onCourseSale() {
    wx.navigateTo({ url: `/pages/course-sale/course-sale?member_id=${this.data.memberId}` });
  },

  onBooking() {
    wx.navigateTo({ url: `/pages/booking/create?member_id=${this.data.memberId}` });
  },

  onCheckin() {
    wx.navigateTo({ url: `/pages/checkin/checkin?member_id=${this.data.memberId}` });
  },
});
