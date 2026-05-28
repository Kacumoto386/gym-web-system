// pages/course-sale/course-sale.js
const api = require('../../utils/api');

Page({
  data: {
    memberId: '',
    memberName: '',
    packages: [],
    selectedPkg: null,
    quantity: 1,
    submitting: false,
  },

  onLoad(query) {
    if (query.member_id) {
      this.setData({ memberId: query.member_id });
    }
    this.loadPackages();
  },

  async loadPackages() {
    try {
      const packages = await api.getPackages();
      this.setData({ packages });
    } catch (e) {}
  },

  selectPkg(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ selectedPkg: this.data.packages[idx] });
  },

  onQuantityInput(e) {
    this.setData({ quantity: parseInt(e.detail.value) || 1 });
  },

  async onSubmit() {
    if (!this.data.memberId || !this.data.selectedPkg) return;
    this.setData({ submitting: true });
    try {
      const pkg = this.data.selectedPkg;
      await api.createSale({
        member_id: this.data.memberId,
        package_id: pkg.package_id,
        product_name: pkg.name,
        quantity: this.data.quantity,
        amount: pkg.price * this.data.quantity,
        paid_amount: pkg.price * this.data.quantity,
      });
      wx.showToast({ title: '购课成功' });
      wx.navigateBack();
    } catch (e) {}
    this.setData({ submitting: false });
  },
});
