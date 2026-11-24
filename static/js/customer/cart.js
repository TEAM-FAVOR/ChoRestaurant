/**
 * Cho Restaurant & Grill — Customer Cart Management Module
 * Production-ready Client State Manager & API Bridge
 * Localization: Ghana (GHS / GH₵)
 */

(function (window) {
  'use strict';

  const STORAGE_KEY = 'cho_restaurant_cart_v1';
  const PROMO_STORAGE_KEY = 'cho_restaurant_active_promo';

  // Config defaults from Ghana settings
  const DEFAULT_CONFIG = {
    currencySymbol: 'GH₵',
    currencyCode: 'GHS',
    deliveryFeeMode: 'DISTANCE',
    flatDeliveryFee: 15.00,
    baseDeliveryFee: 10.00,
    baseDistanceKm: 3.0,
    perKmFee: 3.00,
    maxDeliveryRadiusKm: 15.0,
    freeDeliveryThreshold: 200.00,
    defaultDistanceKm: 4.2
  };

  class CartManager {
    constructor() {
      this.listeners = [];
      this.config = Object.assign({}, DEFAULT_CONFIG, window.CHO_SETTINGS || {});
      this.items = this._loadItems();
      this.activePromo = this._loadPromo();
      this._initStorageListener();
    }

    _loadItems() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
      } catch (e) {
        console.warn('Could not read cart from localStorage', e);
        return [];
      }
    }

    _saveItems() {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.items));
      } catch (e) {
        console.warn('Could not save cart to localStorage', e);
      }
      this._notify();
    }

    _loadPromo() {
      try {
        const raw = localStorage.getItem(PROMO_STORAGE_KEY);
        return raw ? JSON.parse(raw) : null;
      } catch (e) {
        return null;
      }
    }

    _savePromo() {
      try {
        if (this.activePromo) {
          localStorage.setItem(PROMO_STORAGE_KEY, JSON.stringify(this.activePromo));
        } else {
          localStorage.removeItem(PROMO_STORAGE_KEY);
        }
      } catch (e) {
        console.warn('Could not save promo to localStorage', e);
      }
      this._notify();
    }

    _initStorageListener() {
      window.addEventListener('storage', (e) => {
        if (e.key === STORAGE_KEY) {
          this.items = this._loadItems();
          this._notify();
        } else if (e.key === PROMO_STORAGE_KEY) {
          this.activePromo = this._loadPromo();
          this._notify();
        }
      });
    }

    subscribe(callback) {
      if (typeof callback === 'function') {
        this.listeners.push(callback);
        // Initial run
        callback(this);
      }
    }

    _notify() {
      this.listeners.forEach((fn) => {
        try {
          fn(this);
        } catch (err) {
          console.error('Error in cart listener', err);
        }
      });
      // Also update standard DOM elements across pages
      this.renderMiniCart();
      this.updateBadges();
    }

    getItems() {
      return [...this.items];
    }

    getItemCount() {
      return this.items.reduce((sum, item) => sum + (parseInt(item.quantity, 10) || 0), 0);
    }

    getSubtotal() {
      const sum = this.items.reduce((total, item) => {
        const price = parseFloat(item.price) || 0;
        const qty = parseInt(item.quantity, 10) || 1;
        return total + price * qty;
      }, 0);
      return Math.round(sum * 100) / 100;
    }

    addItem(product, quantity = 1, instructions = '') {
      if (!product || !product.id) return;
      const parsedQty = Math.max(1, parseInt(quantity, 10) || 1);
      const existingIndex = this.items.findIndex((item) => String(item.id) === String(product.id));

      if (existingIndex > -1) {
        this.items[existingIndex].quantity += parsedQty;
        if (instructions) {
          this.items[existingIndex].instructions = instructions;
        }
      } else {
        this.items.push({
          id: String(product.id),
          name: product.name || 'Dish',
          price: parseFloat(product.price) || 0,
          image: product.image || '/static/img/dishes/default-dish.svg',
          category: product.category || '',
          prep_time: product.prep_time || '20 mins',
          quantity: parsedQty,
          instructions: instructions || ''
        });
      }

      this._saveItems();
    }

    updateQuantity(productId, quantity) {
      const parsedQty = parseInt(quantity, 10);
      const index = this.items.findIndex((item) => String(item.id) === String(productId));

      if (index === -1) return;

      if (parsedQty <= 0) {
        this.items.splice(index, 1);
      } else {
        this.items[index].quantity = parsedQty;
      }

      this._saveItems();
    }

    removeItem(productId) {
      this.items = this.items.filter((item) => String(item.id) !== String(productId));
      this._saveItems();
    }

    clearCart() {
      this.items = [];
      this._saveItems();
    }

    // Delivery Fee Calculator adhering to PRD §4.12
    getDeliveryFee(distanceKm = null) {
      const subtotal = this.getSubtotal();
      if (subtotal === 0) return 0.00;

      // Free delivery if promo code applied or subtotal meets threshold
      if (this.activePromo && this.activePromo.freeDelivery) {
        return 0.00;
      }
      if (this.config.freeDeliveryThreshold > 0 && subtotal >= this.config.freeDeliveryThreshold) {
        return 0.00;
      }

      const mode = this.config.deliveryFeeMode;
      if (mode === 'FLAT') {
        return parseFloat(this.config.flatDeliveryFee) || 15.00;
      }

      // Distance-based logic
      const dist = distanceKm !== null ? parseFloat(distanceKm) : this.config.defaultDistanceKm;
      const baseFee = parseFloat(this.config.baseDeliveryFee) || 10.00;
      const baseDist = parseFloat(this.config.baseDistanceKm) || 3.00;
      const perKm = parseFloat(this.config.perKmFee) || 3.00;

      const extraKm = Math.max(0, Math.ceil(dist - baseDist));
      const fee = baseFee + (extraKm * perKm);
      return Math.round(fee * 100) / 100;
    }

    applyPromoCode(codeStr) {
      if (!codeStr) return { success: false, message: 'Please enter a promo code.' };
      const code = codeStr.trim().toUpperCase();

      if (code === 'AKWAABA10') {
        this.activePromo = {
          code: 'AKWAABA10',
          type: 'PERCENTAGE',
          value: 10,
          description: '10% Welcome Discount',
          freeDelivery: false
        };
        this._savePromo();
        return { success: true, message: 'Promo code applied: 10% discount on food subtotal!' };
      }

      if (code === 'FREEDEL') {
        this.activePromo = {
          code: 'FREEDEL',
          type: 'FREE_DELIVERY',
          value: 0,
          description: 'Free Delivery Offer',
          freeDelivery: true
        };
        this._savePromo();
        return { success: true, message: 'Promo code applied: Free delivery on your order!' };
      }

      if (code === 'CHO20') {
        const subtotal = this.getSubtotal();
        if (subtotal < 80) {
          return { success: false, message: 'CHO20 requires a minimum order of GH₵80.00.' };
        }
        this.activePromo = {
          code: 'CHO20',
          type: 'FIXED',
          value: 20.00,
          description: 'GH₵20 Off Order',
          freeDelivery: false
        };
        this._savePromo();
        return { success: true, message: 'Promo code applied: GH₵20 discount!' };
      }

      return { success: false, message: 'Invalid or expired promo code.' };
    }

    removePromoCode() {
      this.activePromo = null;
      this._savePromo();
    }

    getDiscountAmount() {
      if (!this.activePromo) return 0.00;
      const subtotal = this.getSubtotal();

      if (this.activePromo.type === 'PERCENTAGE') {
        return Math.round((subtotal * (this.activePromo.value / 100)) * 100) / 100;
      }
      if (this.activePromo.type === 'FIXED') {
        return Math.min(subtotal, parseFloat(this.activePromo.value) || 0);
      }
      return 0.00;
    }

    getGrandTotal(distanceKm = null) {
      const subtotal = this.getSubtotal();
      if (subtotal === 0) return 0.00;
      const discount = this.getDiscountAmount();
      const deliveryFee = this.getDeliveryFee(distanceKm);
      const total = Math.max(0, subtotal - discount + deliveryFee);
      return Math.round(total * 100) / 100;
    }

    formatMoney(amount) {
      const num = parseFloat(amount) || 0;
      return `${this.config.currencySymbol} ${num.toFixed(2)}`;
    }

    updateBadges() {
      const count = this.getItemCount();
      const badges = document.querySelectorAll('.cart-badge');
      badges.forEach((badge) => {
        badge.textContent = count;
        if (count > 0) {
          badge.style.display = 'inline-flex';
          badge.classList.remove('bump');
          void badge.offsetWidth; // trigger reflow
          badge.classList.add('bump');
        } else {
          badge.textContent = '0';
        }
      });
    }

    renderMiniCart() {
      const drawerList = document.querySelector('#cartDrawerItems');
      const drawerSubtotal = document.querySelector('#cartDrawerSubtotal');
      const drawerFreeDel = document.querySelector('#cartDrawerFreeDelivery');
      if (!drawerList) return;

      const items = this.getItems();
      if (items.length === 0) {
        drawerList.innerHTML = `
          <div style="text-align: center; padding: 3rem 1rem;">
            <img src="/static/img/empty-cart.svg" alt="Empty Cart" style="width: 140px; margin: 0 auto 1.25rem;" />
            <h4 style="font-weight: 700; color: #475569; margin-bottom: 0.5rem;">Your cart is empty</h4>
            <p style="font-size: 0.875rem; color: #94a3b8; margin-bottom: 1.25rem;">Explore our delicious dishes and add them to your cart.</p>
            <a href="/menu/" class="btn btn-primary btn-sm">Explore Menu</a>
          </div>
        `;
        if (drawerSubtotal) drawerSubtotal.textContent = this.formatMoney(0);
        if (drawerFreeDel) drawerFreeDel.style.display = 'none';
        return;
      }

      let html = '<div class="cart-items-list">';
      items.forEach((item) => {
        html += `
          <div class="cart-item-row" data-id="${item.id}">
            <img src="${item.image}" alt="${item.name}" class="cart-item-thumb" onerror="this.src='/static/img/dishes/default-dish.svg'" />
            <div class="cart-item-details">
              <div class="cart-item-title">${item.name}</div>
              <div class="cart-item-price">${this.formatMoney(item.price)}</div>
              <div style="margin-top: 0.4rem;">
                <div class="qty-stepper">
                  <button type="button" class="qty-btn" onclick="window.ChoCart.updateQuantity('${item.id}', ${item.quantity - 1})">-</button>
                  <input type="text" class="qty-input" value="${item.quantity}" readonly />
                  <button type="button" class="qty-btn" onclick="window.ChoCart.updateQuantity('${item.id}', ${item.quantity + 1})">+</button>
                </div>
              </div>
            </div>
            <button type="button" class="cart-item-remove" title="Remove Item" onclick="window.ChoCart.removeItem('${item.id}')">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        `;
      });
      html += '</div>';

      drawerList.innerHTML = html;
      const subtotal = this.getSubtotal();
      if (drawerSubtotal) drawerSubtotal.textContent = this.formatMoney(subtotal);

      if (drawerFreeDel) {
        const threshold = this.config.freeDeliveryThreshold;
        if (subtotal >= threshold) {
          drawerFreeDel.innerHTML = '🎉 You have unlocked <strong>FREE Delivery</strong>!';
          drawerFreeDel.style.display = 'flex';
        } else {
          const needed = threshold - subtotal;
          drawerFreeDel.innerHTML = `Add <strong>${this.formatMoney(needed)}</strong> more for FREE delivery!`;
          drawerFreeDel.style.display = 'flex';
        }
      }
    }
  }

  // Singleton instance
  window.ChoCart = new CartManager();

})(window);
