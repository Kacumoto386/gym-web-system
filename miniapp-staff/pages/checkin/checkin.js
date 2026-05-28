// pages/checkin/checkin.js
const api = require('../../utils/api');

Page({
  data: {
    memberId: '',
    memberInfo: null,
    consumeType: '次卡扣次',
    consumeTypes: ['次卡扣次', '储值扣款', '期限卡签到', '现金卡扣费', '无卡体验'],
    selectedCard: null,
    cards: [],
    recentRecords: [],
    submitting: false,
  },

  onShow() {
    this.loadRecent();
  },

  async onSearchMember() {
    if (!this.data.memberId) return;
    try {
      const data = await api.getMember(this.data.memberId);
      this.setData({ memberInfo: data, cards: data.cards || [] });
    } catch (e) {}
  },

  onInputMemberId(e) {
    this.setData({ memberId: e.detail.value });
  },

  onConsumeTypeChange(e) {
    this.setData({ consumeType: this.data.consumeTypes[e.detail.value] });
  },

  selectCard(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ selectedCard: this.data.cards[idx] });
  },

  async onSubmit() {
    if (!this.data.memberInfo) {
      wx.showToast({ title: '请先查询会员', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    try {
      const result = await api.scanCheckin({
        member_id: this.data.memberInfo.member_id,
        consume_type: this.data.consumeType,
        card_id: this.data.selectedCard?.card_id || '',
      });
      wx.showToast({ title: result.consume_note });
      this.setData({ memberInfo: null, selectedCard: null, memberId: '' });
      this.loadRecent();
    } catch (e) {}
    this.setData({ submitting: false });
  },

  async loadRecent() {
    try {
      const records = await api.getRecentCheckins();
      this.setData({ recentRecords: records });
    } catch (e) {}
  },
});
