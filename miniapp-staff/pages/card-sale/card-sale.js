// pages/card-sale/card-sale.js
const api = require('../../utils/api');

Page({
  data: {
    memberId: '',
    memberName: '',
    products: [],
    selectedProduct: null,
    form: {
      product_name: '',
      card_type: '次卡',
      total_classes: 0,
      bonus_classes: 0,
      amount: 0,
      paid_amount: 0,
      salesperson: '',
      validity_days: 365,
      remark: '',
    },
    submitting: false,
  },

  onLoad(query) {
    if (query.member_id) {
      this.setData({ memberId: query.member_id });
    }
    this.loadProducts();
    const staffInfo = wx.getStorageSync('staffInfo');
    if (staffInfo) {
      this.setData({ 'form.salesperson': staffInfo.staff_name });
    }
  },

  async loadProducts() {
    try {
      const products = await api.getCardProducts();
      this.setData({ products });
    } catch (e) {}
  },

  selectProduct(e) {
    const idx = e.currentTarget.dataset.index;
    const product = this.data.products[idx];
    if (!product) return;
    this.setData({
      selectedProduct: product,
      'form.product_name': product.name,
      'form.card_type': product.category,
      'form.total_classes': product.total_classes,
      'form.bonus_classes': product.bonus_classes,
      'form.amount': product.price,
      'form.paid_amount': product.price,
      'form.validity_days': product.validity_days,
    });
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: e.detail.value });
  },

  async onSubmit() {
    if (!this.data.memberId) {
      wx.showToast({ title: '请先选择会员', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    try {
      const result = await api.sellCard({
        member_id: this.data.memberId,
        ...this.data.form,
        total_classes: parseInt(this.data.form.total_classes) || 0,
        bonus_classes: parseInt(this.data.form.bonus_classes) || 0,
        amount: parseFloat(this.data.form.amount) || 0,
        paid_amount: parseFloat(this.data.form.paid_amount) || 0,
        validity_days: parseInt(this.data.form.validity_days) || 365,
      });
      wx.showToast({ title: `购卡成功，剩余${result.remaining_lessons}次` });
      wx.navigateBack();
    } catch (e) {}
    this.setData({ submitting: false });
  },
});
