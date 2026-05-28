// pages/booking/booking.js
const api = require('../../utils/api');

Page({
  data: { bookings: [], showForm: false, coaches: [], selectedCoach: null, bookingDate: '', startTime: '14:00', endTime: '15:00', submitting: false },

  onShow() {
    this.loadBookings();
    this.setData({ bookingDate: new Date().toISOString().slice(0, 10) });
  },

  async loadBookings() {
    try { const data = await api.getBookings(); this.setData({ bookings: data }); } catch (e) {}
  },

  toggleForm() {
    const show = !this.data.showForm;
    this.setData({ showForm: show });
    if (show) this.loadCoaches();
  },

  async loadCoaches() {
    try { const data = await api.getCoaches(); this.setData({ coaches: data }); } catch (e) {}
  },

  selectCoach(e) {
    this.setData({ selectedCoach: this.data.coaches[e.currentTarget.dataset.index] });
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.field]: e.detail.value });
  },

  async onCreateBooking() {
    if (!this.data.selectedCoach) { wx.showToast({ title: '请选择教练', icon: 'none' }); return; }
    this.setData({ submitting: true });
    try {
      await api.createBooking({
        coach_id: this.data.selectedCoach.staff_id,
        booking_date: this.data.bookingDate,
        start_time: this.data.startTime,
        end_time: this.data.endTime,
      });
      wx.showToast({ title: '预约成功' });
      this.setData({ showForm: false });
      this.loadBookings();
    } catch (e) {}
    this.setData({ submitting: false });
  },

  onCancel(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({ title: '确认取消', content: '确定取消该预约吗？', success: async (res) => {
      if (res.confirm) {
        try { await api.cancelBooking(id); wx.showToast({ title: '已取消' }); this.loadBookings(); } catch (e) {}
      }
    }});
  },
});
