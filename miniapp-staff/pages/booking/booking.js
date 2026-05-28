// pages/booking/booking.js
const api = require('../../utils/api');

Page({
  data: {
    bookings: [],
    statusFilter: '',
  },

  onShow() {
    this.loadBookings();
  },

  async loadBookings() {
    try {
      // 员工端查询预约列表，需要按员工ID过滤
      const staffInfo = wx.getStorageSync('staffInfo');
      const data = await api.getCoachSlots(staffInfo?.staff_id || '', '');
      this.setData({ bookings: data?.booked_slots || [] });
    } catch (e) {}
  },

  onCreateBooking() {
    wx.navigateTo({ url: '/pages/booking/create' });
  },
});
