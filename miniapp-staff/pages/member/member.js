// pages/member/member.js
const api = require('../../utils/api');

Page({
  data: {
    keyword: '',
    members: [],
    showCreateForm: false,
    form: { name: '', phone: '', gender: '男', height: '', weight: '', bodyFat: '' },
    submitting: false,
  },

  onLoad(query) {
    if (query.keyword) {
      this.setData({ keyword: query.keyword });
      this.onSearch();
    }
  },

  onSearchInput(e) {
    this.setData({ keyword: e.detail.value });
  },

  async onSearch() {
    if (!this.data.keyword) return;
    try {
      const members = await api.searchMember(this.data.keyword);
      this.setData({ members });
    } catch (e) {}
  },

  toggleCreateForm() {
    this.setData({ showCreateForm: !this.data.showCreateForm });
  },

  onFormInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: e.detail.value });
  },

  async onCreateMember() {
    const { form } = this.data;
    if (!form.name || !form.phone) {
      wx.showToast({ title: '请填写姓名和手机号', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    try {
      await api.createMember({
        name: form.name,
        phone: form.phone,
        gender: form.gender,
        height: form.height ? parseFloat(form.height) : null,
        weight: form.weight ? parseFloat(form.weight) : null,
        body_fat: form.bodyFat ? parseFloat(form.bodyFat) : null,
      });
      wx.showToast({ title: '创建成功' });
      this.setData({ showCreateForm: false, form: { name: '', phone: '', gender: '男', height: '', weight: '', bodyFat: '' } });
      if (form.phone) {
        this.setData({ keyword: form.phone });
        this.onSearch();
      }
    } catch (e) {}
    this.setData({ submitting: false });
  },

  onViewMember(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/member/detail?member_id=${id}` });
  },
});
