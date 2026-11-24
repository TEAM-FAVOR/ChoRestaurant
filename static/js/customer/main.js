/**
 * Cho Restaurant & Grill — Customer Interaction Controller
 * Handles Navigation, Slide Drawers, Filtering, Modals, Toasts & Motion
 */

(function () {
  'use strict';

  // --------------------------------------------------------------------------
  // 0. Scroll-Reveal Engine (IntersectionObserver)
  //    Drives .reveal-on-scroll and .reveal-stagger-child classes.
  //    Staggered siblings within the same parent reveal sequentially.
  // --------------------------------------------------------------------------
  function initScrollReveal() {
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) {
      // Instantly show everything when user prefers reduced motion
      document.querySelectorAll('.reveal-on-scroll, .reveal-stagger-child').forEach(el => {
        el.classList.add('is-visible');
      });
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;

        const el = entry.target;

        if (el.classList.contains('reveal-stagger-child')) {
          // Stagger siblings within the same parent grid/list
          const siblings = Array.from(
            el.parentElement.querySelectorAll('.reveal-stagger-child')
          );
          const idx = siblings.indexOf(el);
          const delay = Math.min(idx * 80, 320);
          setTimeout(() => el.classList.add('is-visible'), delay);
        } else {
          el.classList.add('is-visible');
        }

        observer.unobserve(el);
      });
    }, {
      threshold: 0.12,
      rootMargin: '0px 0px -40px 0px'
    });

    document.querySelectorAll('.reveal-on-scroll, .reveal-stagger-child').forEach(el => {
      observer.observe(el);
    });
  }

  // Run immediately so above-fold elements begin animating before DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initScrollReveal);
  } else {
    initScrollReveal();
  }

  // --------------------------------------------------------------------------
  // 1. Toast Notification Utility
  // --------------------------------------------------------------------------
  window.showToast = function (message, type = 'success', duration = 3500) {
    let container = document.getElementById('toastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toastContainer';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = '✓';
    if (type === 'error') icon = '✕';
    if (type === 'warning') icon = '⚠';
    if (type === 'info') icon = 'ℹ';

    toast.innerHTML = `
      <span style="font-weight: 800; font-size: 1.1rem;">${icon}</span>
      <span style="flex-grow: 1;">${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  };

  // --------------------------------------------------------------------------
  // 2. CSRF Helper for Mutating Fetch Requests
  // --------------------------------------------------------------------------
  window.getCsrfToken = function () {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) return metaTag.getAttribute('content');
    const cookie = document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
  };

  // --------------------------------------------------------------------------
  // 3. Document Ready Initialization
  // --------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', () => {

    // --- A. Sticky Header Shadow on Scroll ---
    const header = document.querySelector('.site-header');
    if (header) {
      window.addEventListener('scroll', () => {
        if (window.scrollY > 20) {
          header.classList.add('scrolled');
        } else {
          header.classList.remove('scrolled');
        }
      });
    }

    // --- B. Mobile Drawer Toggle ---
    const mobileToggle = document.querySelector('.mobile-nav-toggle');
    const mobileDrawer = document.querySelector('.mobile-drawer');
    const mobileDrawerClose = document.querySelector('.mobile-drawer-close');
    const backdrop = document.querySelector('.drawer-backdrop');

    function openMobileDrawer() {
      if (mobileDrawer) mobileDrawer.classList.add('open');
      if (backdrop) backdrop.classList.add('active');
    }
    function closeMobileDrawer() {
      if (mobileDrawer) mobileDrawer.classList.remove('open');
      if (backdrop) backdrop.classList.remove('active');
    }

    if (mobileToggle) mobileToggle.addEventListener('click', openMobileDrawer);
    if (mobileDrawerClose) mobileDrawerClose.addEventListener('click', closeMobileDrawer);
    if (backdrop) backdrop.addEventListener('click', () => {
      closeMobileDrawer();
      closeCartDrawer();
    });

    // --- C. Mini-Cart Drawer Toggle ---
    const cartTrigger = document.querySelector('#cartBtnTrigger');
    const cartDrawer = document.querySelector('#cartDrawer');
    const cartDrawerClose = document.querySelector('#cartDrawerClose');

    function openCartDrawer() {
      if (cartDrawer) {
        cartDrawer.classList.add('open');
        if (backdrop) backdrop.classList.add('active');
        if (window.ChoCart) window.ChoCart.renderMiniCart();
      }
    }
    function closeCartDrawer() {
      if (cartDrawer) cartDrawer.classList.remove('open');
      if (backdrop && (!mobileDrawer || !mobileDrawer.classList.contains('open'))) {
        backdrop.classList.remove('active');
      }
    }

    if (cartTrigger) {
      cartTrigger.addEventListener('click', (e) => {
        e.preventDefault();
        openCartDrawer();
      });
    }
    if (cartDrawerClose) cartDrawerClose.addEventListener('click', closeCartDrawer);

    // --- D. User Dropdown Menu ---
    const userBtn = document.querySelector('.user-avatar-btn');
    const userPanel = document.querySelector('.user-dropdown-panel');

    if (userBtn && userPanel) {
      userBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        userPanel.classList.toggle('show');
      });
      document.addEventListener('click', () => {
        userPanel.classList.remove('show');
      });
    }

    // --- E. Tactile Add to Cart Button Delegations & Cart Pulse ---
    document.addEventListener('pointerdown', (e) => {
      const btn = e.target.closest('.btn-add-to-cart');
      if (btn) btn.classList.add('btn-pressed');
    });
    document.addEventListener('pointerup', (e) => {
      const btn = e.target.closest('.btn-add-to-cart');
      if (btn) btn.classList.remove('btn-pressed');
    });

    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-add-to-cart');
      if (!btn) return;
      e.preventDefault();

      const id = btn.getAttribute('data-id');
      const name = btn.getAttribute('data-name');
      const price = btn.getAttribute('data-price');
      const image = btn.getAttribute('data-image');
      const category = btn.getAttribute('data-category') || '';
      const prep = btn.getAttribute('data-prep') || '20 mins';

      let qty = 1;
      const card = btn.closest('.food-card-body, .food-detail-actions, .editorial-dish-card');
      const qtyInput = card?.querySelector('.qty-input');
      if (qtyInput) {
        qty = parseInt(qtyInput.value, 10) || 1;
      }

      let instructions = '';
      const notesEl = document.querySelector('#kitchenInstructions');
      if (notesEl) instructions = notesEl.value;

      if (window.ChoCart) {
        window.ChoCart.addItem(
          { id, name, price, image, category, prep_time: prep },
          qty,
          instructions
        );

        window.showToast(`Added ${qty}x ${name} to your order!`, 'success');

        // Tactile button compression & confirmation morph
        const originalContent = btn.innerHTML;
        btn.classList.add('btn-added-state');
        btn.innerHTML = `<span class="btn-check-icon">✓</span> Added`;

        // Pulse cart button trigger in top navbar
        const cartBtn = document.querySelector('#cartBtnTrigger');
        if (cartBtn) {
          cartBtn.classList.remove('pulse');
          void cartBtn.offsetWidth; // trigger reflow
          cartBtn.classList.add('pulse');
        }

        setTimeout(() => {
          btn.innerHTML = originalContent;
          btn.classList.remove('btn-added-state');
        }, 1100);
      }
    });

    // --- F. Quantity Stepper Button Event Delegation ---
    document.addEventListener('click', (e) => {
      const minusBtn = e.target.closest('.qty-btn-minus');
      const plusBtn = e.target.closest('.qty-btn-plus');

      if (minusBtn) {
        const input = minusBtn.parentElement.querySelector('.qty-input');
        if (input) {
          const val = Math.max(1, (parseInt(input.value, 10) || 1) - 1);
          input.value = val;
          input.dispatchEvent(new Event('change'));
        }
      }
      if (plusBtn) {
        const input = plusBtn.parentElement.querySelector('.qty-input');
        if (input) {
          const val = (parseInt(input.value, 10) || 1) + 1;
          input.value = val;
          input.dispatchEvent(new Event('change'));
        }
      }
    });

    // --- G. Live Menu Search & Client-side Filtering with Smooth Transition ---
    const menuSearchInput = document.querySelector('#menuSearchInput');
    const categoryPills = document.querySelectorAll('.filter-pill[data-filter-mode="client"], .category-tab-btn');
    const foodCards = document.querySelectorAll('.editorial-dish-card, .food-card');
    const menuGrid = document.querySelector('#menuFoodGrid, .editorial-food-grid');

    function filterMenuCards() {
      const query = (menuSearchInput?.value || '').toLowerCase().trim();
      const activePill = document.querySelector('.filter-pill.active, .category-tab-btn.active');
      const selectedCategory = activePill ? (activePill.getAttribute('data-category') || 'all') : 'all';

      if (menuGrid) {
        menuGrid.style.opacity = '0.4';
        menuGrid.style.transform = 'translateY(4px)';
        menuGrid.style.transition = 'opacity 120ms ease, transform 120ms ease';
      }

      setTimeout(() => {
        let visibleCount = 0;
        foodCards.forEach((card, idx) => {
          const name = (card.getAttribute('data-name') || '').toLowerCase();
          const desc = (card.getAttribute('data-desc') || '').toLowerCase();
          const cat = (card.getAttribute('data-category-slug') || '').toLowerCase();

          const matchesQuery = !query || name.includes(query) || desc.includes(query);
          const matchesCategory = selectedCategory === 'all' || cat === selectedCategory;

          if (matchesQuery && matchesCategory) {
            card.style.display = 'flex';
            card.style.animation = `cardFadeIn 260ms cubic-bezier(0.22, 1, 0.36, 1) ${Math.min(visibleCount * 25, 150)}ms both`;
            visibleCount++;
          } else {
            card.style.display = 'none';
          }
        });

        const noResultsBox = document.querySelector('#noMenuResults');
        if (noResultsBox) {
          noResultsBox.style.display = visibleCount === 0 ? 'block' : 'none';
        }

        if (menuGrid) {
          menuGrid.style.opacity = '1';
          menuGrid.style.transform = 'translateY(0)';
        }
      }, 100);
    }

    if (menuSearchInput) {
      menuSearchInput.addEventListener('input', filterMenuCards);
    }

    if (categoryPills.length > 0) {
      categoryPills.forEach((pill) => {
        pill.addEventListener('click', (e) => {
          if (foodCards.length > 0 && pill.getAttribute('data-filter-mode') === 'client') {
            e.preventDefault();
            categoryPills.forEach((p) => p.classList.remove('active'));
            pill.classList.add('active');
            filterMenuCards();
          }
        });
      });
    }

    // --- H. Gentle Top Announcement Ticker Cycling ---
    const ticker = document.getElementById('topAnnouncementTicker');
    if (ticker) {
      const slides = ticker.querySelectorAll('.top-ticker-slide');
      if (slides.length > 1) {
        let currentSlide = 0;
        let tickerInterval = setInterval(cycleTicker, 4600);

        function cycleTicker() {
          slides[currentSlide].classList.remove('active');
          currentSlide = (currentSlide + 1) % slides.length;
          slides[currentSlide].classList.add('active');
        }

        ticker.addEventListener('mouseenter', () => clearInterval(tickerInterval));
        ticker.addEventListener('mouseleave', () => {
          tickerInterval = setInterval(cycleTicker, 4600);
        });
      }
    }

    // Initialize badges on load
    if (window.ChoCart) {
      window.ChoCart.updateBadges();
    }
  });

})();
