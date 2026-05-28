// pages/purchase/order.js
const api = require('../../utils/api');

Page({
  data: {
    orders: [],
    statusFilter: '',
  },

  onShow() {
    this.loadOrders();
  },

  async loadOrders() {
    try {
      const orders = await api.getOrders(this.data.statusFilter);
      this.setData({ orders });
    } catch (e) {}
  },

  filterOrders(e) {
    const status = e.currentTarget.dataset.status;
    this.setData({ statusFilter: status });
    this.loadOrders();
  },

  getStatusText(status) {
    const map = { pending: '待支付', paid: '已支付', completed: '已完成', cancelled: '已取消' };
    return map[status] || status;
  },

  getProductTypeText(t) {
    return t === 'card' ? '购卡' : '购课';
  },
});
