// pages/purchase/purchase.js
const api = require('../../utils/api');

Page({
  data: {
    tab: 'card',          // card | package
    cardProducts: [],
    packages: [],
    selectedProduct: null,
    selectedPkg: null,
    quantity: 1,
    submitting: false,
  },

  onShow() {
    this.loadProducts();
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ tab, selectedProduct: null, selectedPkg: null });
    if (tab === 'package' && this.data.packages.length === 0) {
      this.loadPackages();
    }
  },

  async loadProducts() {
    try { const data = await api.getCardProducts(); this.setData({ cardProducts: data }); } catch (e) {}
  },

  async loadPackages() {
    try { const data = await api.getPackages(); this.setData({ packages: data }); } catch (e) {}
  },

  selectProduct(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ selectedProduct: this.data.cardProducts[idx], selectedPkg: null, quantity: 1 });
  },

  selectPkg(e) {
    const idx = e.currentTarget.dataset.index;
    this.setData({ selectedPkg: this.data.packages[idx], selectedProduct: null, quantity: 1 });
  },

  onQuantityInput(e) {
    this.setData({ quantity: parseInt(e.detail.value) || 1 });
  },

  async onBuy() {
    const { tab, selectedProduct, selectedPkg, quantity } = this.data;
    if (tab === 'card' && !selectedProduct) { wx.showToast({ title: '请选择卡种', icon: 'none' }); return; }
    if (tab === 'package' && !selectedPkg) { wx.showToast({ title: '请选择课程包', icon: 'none' }); return; }

    this.setData({ submitting: true });
    try {
      const product = tab === 'card' ? selectedProduct : selectedPkg;
      const order = await api.createOrder({
        product_type: tab === 'card' ? 'card' : 'package',
        product_id: tab === 'card' ? String(product.id) : product.package_id,
        quantity,
      });

      wx.showModal({
        title: '确认支付',
        content: `${product.name}\n金额: ¥${(product.price * quantity).toFixed(2)}`,
        success: async (res) => {
          if (res.confirm) {
            // 预开发阶段：直接调 pay() 模拟支付成功
            try {
              const result = await api.pay(order.order_id);
              wx.showToast({ title: result.message || '购买成功' });
              this.setData({ selectedProduct: null, selectedPkg: null, quantity: 1 });
              this.loadProducts();
              if (tab === 'package') this.loadPackages();
            } catch (e) {}
          } else {
            // 用户取消支付，仅提示
            wx.showToast({ title: '订单已创建，可稍后支付', icon: 'none' });
          }
        },
      });
    } catch (e) {}
    this.setData({ submitting: false });
  },

  onViewOrders() {
    wx.navigateTo({ url: '/pages/purchase/order' });
  },
});
