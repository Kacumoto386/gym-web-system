// pages/booking/create.js
const api = require('../../utils/api');

Page({
  data: {
    memberId: '',
    coaches: [],
    selectedCoach: null,
    bookingDate: '',
    startTime: '',
    endTime: '',
    submitting: false,
  },

  onLoad(query) {
    if (query.member_id) {
      this.setData({ memberId: query.member_id });
    }
    this.loadCoaches();
    this.setData({
      bookingDate: new Date().toISOString().slice(0, 10),
      startTime: '14:00',
      endTime: '15:00',
    });
  },

  async loadCoaches() {
    try {
      const coaches = await api.getCoaches();
      this.setData({ coaches });
    } catch (e) {}
  },

  selectCoach(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ selectedCoach: this.data.coaches[idx] });
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [field]: e.detail.value });
  },

  async onSubmit() {
    if (!this.data.memberId || !this.data.selectedCoach) {
      wx.showToast({ title: '请选择会员和教练', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    try {
      await api.createBooking({
        member_id: this.data.memberId,
        coach_id: this.data.selectedCoach.staff_id,
        booking_date: this.data.bookingDate,
        start_time: this.data.startTime,
        end_time: this.data.endTime,
      });
      wx.showToast({ title: '预约成功' });
      wx.navigateBack();
    } catch (e) {}
    this.setData({ submitting: false });
  },
});
