// Nav scroll effect
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 20);
});

// Mobile nav toggle
const navToggle = document.getElementById('nav-toggle');
const navLinks = document.getElementById('nav-links');
navToggle.addEventListener('click', () => {
  navToggle.classList.toggle('active');
  navLinks.classList.toggle('open');
});
navLinks.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    navToggle.classList.remove('active');
    navLinks.classList.remove('open');
  });
});

// Scroll reveal
const reveals = document.querySelectorAll('.reveal');
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry, i) => {
    if (entry.isIntersecting) {
      setTimeout(() => entry.target.classList.add('visible'), i * 60);
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });
reveals.forEach(el => observer.observe(el));

// Live metrics dashboard
async function fetchMetrics() {
  const dashboard = document.getElementById('metrics-dashboard');
  if (!dashboard) return;

  try {
    const resp = await fetch('/api/metrics');
    if (!resp.ok) throw new Error('Failed to fetch');
    const data = await resp.json();

    const nodes = data.infrastructure?.nodes_healthy ?? '\u2014';
    const services = data.infrastructure?.services_up ?? '\u2014';
    const compliance = data.security?.compliance_score ?? '\u2014';
    const agents = data.security?.agents_active ?? '\u2014';

    dashboard.innerHTML = `
      <div class="dash-metric">
        <div class="val">${nodes}/${nodes}</div>
        <div class="label">Nodes Online</div>
      </div>
      <div class="dash-metric">
        <div class="val">${services}</div>
        <div class="label">Services Active</div>
      </div>
      <div class="dash-metric">
        <div class="val">${compliance}%</div>
        <div class="label">NIST Compliance</div>
      </div>
      <div class="dash-metric">
        <div class="val">${agents}</div>
        <div class="label">Security Agents</div>
      </div>
    `;
  } catch (e) {
    dashboard.innerHTML = '<p class="dash-note">Metrics temporarily unavailable</p>';
  }
}

fetchMetrics();
setInterval(fetchMetrics, 300000);

// Contact form handler
const form = document.getElementById('contact-form');
if (form) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    const status = document.getElementById('form-status');

    btn.disabled = true;
    btn.textContent = 'Sending...';
    status.className = 'form-status';
    status.style.display = 'none';

    const payload = {
      name: form.querySelector('#name').value,
      email: form.querySelector('#email').value,
      company: form.querySelector('#company').value,
      interest: form.querySelector('#interest').value,
      message: form.querySelector('#message').value,
    };

    try {
      const resp = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();

      if (resp.ok) {
        status.textContent = data.message;
        status.className = 'form-status success';
        form.reset();
        btn.textContent = 'Sent \u2014 we\'ll be in touch';
        btn.style.background = '#2D6B4A';
      } else {
        status.textContent = data.detail || 'Something went wrong. Please try again.';
        status.className = 'form-status error';
        btn.textContent = 'Send It Over';
      }
    } catch (e) {
      status.textContent = 'Network error. Please try again later.';
      status.className = 'form-status error';
      btn.textContent = 'Send It Over';
    } finally {
      btn.disabled = false;
    }
  });
}
