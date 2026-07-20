document.addEventListener("DOMContentLoaded", () => {
  if (getToken()) {
    window.location.href = "/drones";
    return;
  }

  const form = document.getElementById("login-form");
  const errorEl = document.getElementById("login-error");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.textContent = "";
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    if (!email || !password) {
      errorEl.textContent = "Email and password are required.";
      return;
    }

    const { ok, body, status } = await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    if (!ok) {
      errorEl.textContent =
        status === 401 ? "Wrong email or password." : body?.message || "Login failed.";
      return;
    }

    setSession(body.token, {
      email: body.email,
      name: body.name,
      pilot_id: body.pilot_id,
    });
    window.location.href = "/drones";
  });
});
