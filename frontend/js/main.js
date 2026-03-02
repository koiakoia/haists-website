async function fetchMetrics() {
  const dashboard = document.getElementById('metrics-dashboard');
  if (!dashboard) return;

  try {
    const resp = await fetch('/api/metrics');
    if (!resp.ok) throw new Error('Failed to fetch');
    const data = await resp.json();

    dashboard.innerHTML = `
      <div class="metric-card">
        <span class="metric-value">${data.infrastructure?.nodes_healthy ?? '\u2014'}</span>
        <span class="metric-label">Nodes Online</span>
      </div>
      <div class="metric-card">
        <span class="metric-value">${data.infrastructure?.services_up ?? '\u2014'}</span>
        <span class="metric-label">Services Active</span>
      </div>
      <div class="metric-card">
        <span class="metric-value">${data.security?.compliance_score ?? '\u2014'}%</span>
        <span class="metric-label">NIST Compliance</span>
      </div>
      <div class="metric-card">
        <span class="metric-value">${data.security?.agents_active ?? '\u2014'}</span>
        <span class="metric-label">Security Agents</span>
      </div>
    `;
  } catch (e) {
    dashboard.innerHTML = '<p class="metric-error">Metrics temporarily unavailable</p>';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  fetchMetrics();
  setInterval(fetchMetrics, 300000);

  const form = document.getElementById('contact-form');
  if (!form) return;

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
      } else {
        status.textContent = data.detail || 'Something went wrong. Please try again.';
        status.className = 'form-status error';
      }
    } catch (e) {
      status.textContent = 'Network error. Please try again later.';
      status.className = 'form-status error';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Send Message';
    }
  });
});
